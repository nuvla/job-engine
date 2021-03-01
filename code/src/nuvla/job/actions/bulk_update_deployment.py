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

    def _call_action(self):
        deployments = self.user_api.search('deployment',
                                           filter=self.payload['filter'],
                                           orderby='updated:desc',
                                           select='id, state ')
        self.result['ALL'] = [deployment.id for deployment in deployments]
        for deployment in deployments.resources:
            try:
                response = self.user_api.operation(deployment, 'update')
                nested_job_id = response.data['location']
                self.job.add_affected_resource(deployment.id)
                self.job.add_nested_job(nested_job_id)
            except Exception as ex:
                self.result['bootstrap-exceptions'][deployment.id] = repr(ex)
                self.result['FAILED'].append(deployment.id)

    def _build_monitored_jobs_filter(self):
        filter_jobs_ids = ' or '.join(map(lambda job: f'id="{job}"', self.monitored_jobs))
        filter_finished_jobs = 'progress=100'
        return f'({filter_jobs_ids}) and {filter_finished_jobs}' \
            if filter_jobs_ids else filter_finished_jobs

    def _progress_increment(self):
        new_progress = int(100 - (len(self.monitored_jobs) / self.progress_increment))
        if new_progress != self.job['progress']:
            self.job.set_progress(new_progress)

    def _check_monitored_jobs(self):
        try:
            query_filter = self._build_monitored_jobs_filter()
            query_result = self.user_api.search('job',
                                                filter=query_filter,
                                                last=10000,
                                                select='id, state, target-resource')
            for resource in query_result.resources:
                deployment_id = resource.data['target-resource']['href']
                if deployment_id not in self.result[resource.data['state']]:
                    self.result[resource.data['state']].append(deployment_id)
                    self.monitored_jobs.remove(deployment_id)
        except Exception:
            pass

    def bulk_update_deployment(self):
        logging.info(f'Start bulk deployment update {self.job.id}')
        self.job.set_progress(10)
        self._call_action()
        self._push_result()
        self.job.set_progress(20)
        self.monitored_jobs = [job['href'] for job in self.job.get('nested-jobs', [])]
        self.progress_increment = len(self.monitored_jobs) / 80
        while self.monitored_jobs:
            self._check_monitored_jobs()
            self._push_result()
            self._update_progress()
            time.sleep(10)

        logging.info(f'End of bulk deployment update {self.job.id}')
        return 0

    def do_work(self):
        return self.bulk_update_deployment()
