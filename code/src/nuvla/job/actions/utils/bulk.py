# -*- coding: utf-8 -*-

import logging
import json
from nuvla.api import Api


class BulkJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.payload = json.loads(self.job['payload'])
        self.user_api = self._get_user_api()
        self.monitored_jobs = []
        self.progress_increment = None
        self.result = {
            'bootstrap-exceptions': {},
            'FAILED': [],
            'SUCCESS': [],
            'ALL': []}

    def _get_user_api(self):
        authn_info = self.payload['authn-info']
        insecure = not self.api.session.verify
        return Api(endpoint=self.api.endpoint, insecure=insecure,
                   persist_cookie=False, reauthenticate=True,
                   authn_header=f'{authn_info["user-id"]} '
                                f'{authn_info["active-claim"]} '
                                f'{" ".join(authn_info["claims"])}')

    def _push_result(self):
        self.job.set_status_message(json.dumps(self.result))

    def resource_done(self):
        return set(self.result.get('SUCCESS', []) + self.result.get('FAILED', []))

    def resource_left(self):
        all_result = set(self.result.get('ALL', []))
        return all_result.difference(self.resource_done())

    @staticmethod
    def filter_jobs_resources(job_ids):
        return ' or '.join(map(lambda job: f'id="{job}"', job_ids))

    def _build_monitored_jobs_filter(self):
        filter_jobs_ids = ' or '.join(map(lambda job: f'id="{job}"', self.monitored_jobs))
        filter_finished_jobs = 'progress=100'
        return f'({filter_jobs_ids}) and {filter_finished_jobs}'

    def _update_progress(self):
        new_progress = 100 if self.progress_increment == 0 else int(
            100 - (len(self.monitored_jobs) / self.progress_increment))
        if new_progress != self.job['progress']:
            self.job.set_progress(new_progress)

    def query_jobs(self, query_filter):
        return self.user_api.search('job',
                                    filter=query_filter,
                                    last=10000,
                                    select='id, state, target-resource, return-code')

    def _check_monitored_jobs(self):
        try:
            completed_jobs = self.query_jobs(self._build_monitored_jobs_filter())
            for resource in completed_jobs.resources:
                resource_id = resource.data['target-resource']['href']
                if resource_id not in self.resource_done():
                    if resource.data.get('return-code') == 0:
                        self.result['SUCCESS'].append(resource_id)
                    else:
                        self.result['FAILED'].append(resource_id)
                self.monitored_jobs.remove(resource.id)
        except Exception as ex:
            logging.error(ex)

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass
