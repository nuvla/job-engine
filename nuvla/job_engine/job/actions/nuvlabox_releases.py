# -*- coding: utf-8 -*-

from ..actions import action

import logging
import requests


@action('update_nuvlabox_releases')
class NuvlaBoxReleasesJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.nuvlabox_releases_url = "https://api.github.com/repos/nuvlaedge/deployment/releases"

    def release_already_exists(self, release, published_at):
        results = self.api.search('nuvlabox-release',
                                  filter='release="{}"'.format(release)).resources

        if len(results) > 1:
            # shouldn't happen, just clean up everything
            for rel in results:
                self.api.delete(rel.id)

            return False
        elif len(results) == 1:
            if results[0].data.get('release-date', '') < published_at:
                logging.info(
                    "NuvlaBox release {} is already catalogued but seems outdated".format(release))
                self.api.delete(results[0].id)
                return False

            return True
        else:
            return False

    def update_nuvlabox_releases(self):
        logging.info('Updating catalogue of NuvlaBox releases')

        self.job.set_progress(10)

        releases = requests.get(self.nuvlabox_releases_url).json()

        current_job_progress = 20
        missing_progress = 100 - current_job_progress
        progress_steps = int(missing_progress / len(releases))

        for rel in releases:
            self.job.set_progress(current_job_progress)
            current_job_progress += progress_steps
            try:
                url = rel['html_url']
                release = rel['tag_name']
                release_date = rel['published_at']
                pre_release = bool(rel['prerelease'])
                release_notes = rel.get('body', '')
                assets = rel['assets']
            except KeyError:
                logging.warning('NuvlaBox release - %s - is incomplete' % rel)
                continue

            if not assets:
                logging.warning(
                    'NuvlaBox release %s is missing assets and thus cannot be published in Nuvla'
                    % release)
                continue

            # Check if this release is already catalogued
            if self.release_already_exists(release, release_date):
                logging.info("NuvlaBox release {} is already catalogued".format(release))
                continue

            compose_files = []
            for asset in assets:
                try:
                    name = asset['name']
                    if not name.startswith('docker-compose.') or not name.endswith('.yml'):
                        logging.debug(f'Skipping asset "{name}". Not a docker-compose yaml file.')
                        continue
                    download_asset_url = asset['browser_download_url']
                except KeyError:
                    logging.warning(
                        'Cannot resolve asset %s for NuvlaBox release %s' % (asset, release))
                    continue

                file = requests.get(download_asset_url).text

                # seems buggy with docker-compose.modbus.yml: lstrip('docker-compose.')
                scope = ' '.join(name.split('.')[1:-1])

                compose_files.append({
                    'name': name,
                    'scope': scope,
                    'file': file
                })

            resource_payload = {
                'release': release,
                'published': True,
                'url': url,
                'pre-release': pre_release,
                'release-date': release_date,
                'release-notes': release_notes,
                'compose-files': compose_files,
                'acl': {
                    'view-data': [
                        'group/nuvla-anon',
                        'group/nuvla-user'
                    ],
                    'view-meta': [
                        'group/nuvla-anon',
                        'group/nuvla-user'
                    ],
                    'view-acl': [
                        'group/nuvla-user'
                    ],
                    'owners': [
                        'group/nuvla-admin'
                    ]
                }
            }

            self.api.add('nuvlabox-release', resource_payload)

        self.job.set_progress(100)

        return 0

    def do_work(self):
        return self.update_nuvlabox_releases()
