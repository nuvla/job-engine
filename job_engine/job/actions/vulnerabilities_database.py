# -*- coding: utf-8 -*-

from ..actions import action

import logging
import requests
import gzip
import json
import io
from nuvla.api import NuvlaError


@action('update_vulnerabilities_database')
class VulnerabilitiesDatabaseJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        config = self.api.get('configuration/nuvla')
        self.external_vulnerabilities_db = config.data.get('external-vulnerabilities-db')
        self.github_api = 'https://api.github.com'

    @staticmethod
    def download_db(url):
        external_db = requests.get(url)

        trimmed_url = url.split('?')[0]    # get rid of any url parameters
        if trimmed_url.endswith('.gz'):
            # gzip file
            db_content = io.BytesIO(external_db.content)

            db_content_json = json.loads(gzip.GzipFile(fileobj=db_content, mode='rb').read())
        else:
            # assume it is a JSON file
            db_content_json = external_db.json()

        return db_content_json

    def get_last_db_timestamps(self):
        nuvla_db_last_update = None

        nuvla_vulns = self.api.search('vulnerability', orderby='modified:desc', last=1).resources
        if len(nuvla_vulns) > 0:
            nuvla_db_last_update = nuvla_vulns[0].data.get('updated')

        # instead of naively always downloading to DB to check the last timestamp, we can try to infer whether the DB
        # is in GitHub, and find the timestamp of the last commit and a pre-condition
        if self.external_vulnerabilities_db.startswith('https://github.com/'):
            gh_account_repo = self.external_vulnerabilities_db.lstrip('https://github.com/').rstrip('.git')
            try:
                github_account, repo = gh_account_repo.split('/')[0:2]

                github_last_commit = requests.get(f'{self.github_api}/repos/{github_account}/{repo}/commits/main')
                if github_last_commit.status_code == 422:
                    # try legacy master branch instead
                    github_last_commit = requests.get(f'{self.github_api}/repos/{github_account}/{repo}/commits/master')

                if github_last_commit.status_code == 200 and isinstance(github_last_commit.json(), dict):
                    last_commit_date = str(github_last_commit.json()['commit'].
                                           get('committer', github_last_commit.json()['commit'].get('author'))['date'])

                    return nuvla_db_last_update, last_commit_date, None
            except (IndexError, KeyError):
                logging.exception("Could not infer last date of DB update from GitHub API")
                pass

        # if we got here, it's because we couldn't yet get the last update timestamp from the external source
        # so let's just download the given DB and get the timestamp from its content
        db_content_json = self.download_db(self.external_vulnerabilities_db)

        try:
            # even though the db_content_json might not be needed (in case there are no updates),
            # we cache it anyway to avoid downloading it again later on
            return nuvla_db_last_update, db_content_json['CVE_data_timestamp'], db_content_json
        except KeyError:
            logging.exception(f"Could not parse the external vulnerability DB provided at {self.external_vulnerabilities_db}")

        return nuvla_db_last_update, None, None

    def get_nuvla_vulnerabilities_list(self):
        # we need to paginate, so let's initialize the list
        # 10k records at the time
        vulns = []
        aux = self.api.search('vulnerability', orderby='updated:desc', select="id,name,modified,updated").resources

        vulns += aux

        while len(aux) == 10000:
            page_filter = aux[-1].data.get('updated')
            # when we get a page with less than 10k resources, then it's the last one
            aux = self.api.search('vulnerability',
                                  orderby='updated:desc',
                                  select="id,name,modified,updated",
                                  filter=f'updated<"{page_filter}"').resources

            vulns += aux

        return vulns

    def update_vulnerabilities_database(self):
        logging.info(f'Updating DB of vulnerabilities in Nuvla, from {self.external_vulnerabilities_db}')

        self.job.set_progress(10)

        nuvla_db_last_update, external_db_last_update, db_content = self.get_last_db_timestamps()

        self.job.set_progress(20)

        if not external_db_last_update:
            # if we can't get the last update time from the external DB, then we can't update the Nuvla DB
            self.job.update_job(status_message="Can not lookup external DB. Nothing to do...")
            self.job.set_progress(100)

            return 0

        logging.info("Last Nuvla DB update: %s" % nuvla_db_last_update)
        logging.info("Last external DB update: %s" % external_db_last_update)

        new_vuln = 0
        updated_vuln = 0

        self.job.set_progress(40)
        if not db_content:
            db_content = self.download_db(self.external_vulnerabilities_db)

        # get all vulnerability IDs from Nuvla
        nuvla_vulnerabilities = self.get_nuvla_vulnerabilities_list()

        nuvla_vuln_res_id_map = {}
        for res in nuvla_vulnerabilities:
            nuvla_vuln_res_id_map[res.data.get('name', '')] = {'nuvla_id': res.id,
                                                               'modified': res.data.get('modified',
                                                                                        '1970-01-01T00:00:00Z')}

        self.job.set_progress(60)
        try:
            cve_items = db_content['CVE_Items']
            logging.info("Vulnerabilities in the Nuvla DB: %s" % len(nuvla_vuln_res_id_map))
            logging.info("Vulnerabilities in external DB: %s" % len(cve_items))

            for cve_item in cve_items:
                try:
                    cve = cve_item['cve']
                    cve_modified = cve_item.get('lastModifiedDate')

                    if not cve_modified:
                        # if we can't know when was the vulnerability updated, then better not to update anything
                        continue

                    cve_id = cve['CVE_data_meta']['ID']

                    # to save API calls, let's do selective updates, by only updating the Nuvla vulnerabilities
                    # that have in fact been updated upstream (instead of the full collection)
                    if not nuvla_db_last_update or \
                            cve_id not in nuvla_vuln_res_id_map or \
                            cve_modified > nuvla_vuln_res_id_map[cve_id]['modified']:
                        # then it needs updating/creating
                        cve_description = cve['description']['description_data'][0]['value']
                        cve_ref = cve['references']['reference_data'][0]['url']
                        cve_score = cve_item['impact']['baseMetricV3']['cvssV3'].get('baseScore')
                        cve_severity = cve_item['impact']['baseMetricV3']['cvssV3'].get('baseSeverity', 'NONE')
                        cve_published = cve_item['publishedDate']

                        payload = {
                            'name': cve_id,
                            'description': cve_description,
                            'reference': cve_ref,
                            'published': cve_published,
                            'modified': cve_modified,
                            "acl": {
                                "view-data": [
                                    "group/nuvla-user"
                                ],
                                "view-meta": [
                                    "group/nuvla-user"
                                ],
                                "view-acl": [
                                    "group/nuvla-user"
                                ],
                                "owners": [
                                    "group/nuvla-admin"
                                ]
                            },
                        }

                        if cve_score:
                            payload['score'] = cve_score
                            payload['severity'] = cve_severity if cve_severity else "NONE"

                        if cve_id in nuvla_vuln_res_id_map:
                            # PUT
                            try:
                                self.api.edit(nuvla_vuln_res_id_map[cve_id]['nuvla_id'], payload)
                                updated_vuln += 1
                            except NuvlaError:
                                logging.exception(f"Couldn't PUT existing vulnerability {payload['name']}")
                        else:
                            # POST
                            try:
                                self.api.add('vulnerability', payload)
                                new_vuln += 1
                            except NuvlaError:
                                logging.exception(f"Couldn't POST new vulnerability {payload['name']}")
                except KeyError:
                    continue
        except KeyError:
            logging.exception("External DB is missing expected fields")
            raise

        msg = f"Summary: modified={updated_vuln} / new={new_vuln}"
        logging.info(msg)

        self.job.set_progress(100)
        self.job.set_status_message(msg)

        return 0

    def do_work(self):
        return self.update_vulnerabilities_database()
