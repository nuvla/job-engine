# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
import json
import time

from nuvla.connector import docker_machine_connector
from ..actions import action
from nuvla.api import Api

COE_TYPE_SWARM = docker_machine_connector.COE_TYPE_SWARM
COE_TYPE_K8S = docker_machine_connector.COE_TYPE_K8S


@action('bulk_update_deployment')
class DeploymentBulkUpdateJob(object):

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

    def deployment_done(self):
        return set(self.result.get('SUCCESS', []) + self.result.get('FAILED', []))

    def deployment_left(self):
        all_result = set(self.result.get('ALL', []))
        return all_result.difference(self.deployment_done())

    def search_deployment(self, filter_str):
        return self.user_api.search('deployment',
                                    filter=filter_str,
                                    orderby='updated:desc',
                                    select='id, state')

    def _call_sub_actions(self):
        dep_to_process = self.deployment_left()
        if dep_to_process:
            filter_dep_to_process = ' or '.join(map(lambda job: f'id="{id}"', dep_to_process))
            deployments = self.search_deployment(filter_dep_to_process)
        else:
            deployments = self.search_deployment(self.payload['filter'])
            self.result['ALL'] = [deployment.id for deployment in deployments.resources]
            self._push_result()

        for deployment in deployments.resources:
            nested_job_id = None
            try:
                module_href = self.payload.get('module-href')
                if module_href:
                    self.user_api.operation(deployment, 'fetch-module',
                                            {'module-href': module_href})
                response = self.user_api.operation(deployment, 'update', {'low-priority': True})
                nested_job_id = response.data['location']
            except Exception as ex:
                self.result['bootstrap-exceptions'][deployment.id] = repr(ex)
                self.result['FAILED'].append(deployment.id)

            if nested_job_id:
                self.job.add_affected_resource(deployment.id)
                self.job.add_nested_job(nested_job_id)

    @staticmethod
    def filter_jobs_deployments(job_ids):
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
                deployment_id = resource.data['target-resource']['href']
                if deployment_id not in self.deployment_done():
                    if resource.data.get('return-code') == 0:
                        self.result['SUCCESS'].append(deployment_id)
                    else:
                        self.result['FAILED'].append(deployment_id)
                self.monitored_jobs.remove(resource.id)
        except Exception as ex:
            logging.error(ex)

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass

    def bulk_update_deployment(self):
        logging.info(f'Start bulk deployment update {self.job.id}')
        # Job recovery support
        if self.job.get('progress', 0) > 0:
            self.reload_result()
        if self.job.get('progress', 0) < 10:
            self.job.set_progress(10)
        if self.job.get('progress', 0) < 20:
            self._call_sub_actions()
            self._push_result()
            self.job.set_progress(20)
        self.monitored_jobs = self.job.get('nested-jobs', [])
        self.progress_increment = len(self.monitored_jobs) / 80
        while self.monitored_jobs:
            time.sleep(5)
            self._check_monitored_jobs()
            logging.info(f'Bulk deployment update {self.job.id}: '
                         f'{len(self.monitored_jobs)} jobs left')
            self._push_result()
            self._update_progress()
        logging.info(f'End of bulk deployment update {self.job.id}')
        return 0

    def do_work(self):
        return self.bulk_update_deployment()
