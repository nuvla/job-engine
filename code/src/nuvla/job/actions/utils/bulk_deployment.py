# -*- coding: utf-8 -*-

import logging
import time
import abc
from .bulk import BulkJob


class DeploymentBulkJob(BulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)

    def search_deployment(self, filter_str):
        return self.user_api.search('deployment',
                                    filter=filter_str,
                                    orderby='updated:desc',
                                    select='id, state')

    @abc.abstractmethod
    def action_deployment(self, deployment):
        return

    def _call_sub_actions(self):
        dep_to_process = self.resource_left()
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
                self.action_deployment(deployment)
            except Exception as ex:
                self.result['bootstrap-exceptions'][deployment.id] = repr(ex)
                self.result['FAILED'].append(deployment.id)

            if nested_job_id:
                self.job.add_affected_resource(deployment.id)
                self.job.add_nested_job(nested_job_id)

    def run(self, action):
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
            logging.info(f'Bulk deployment {action} {self.job.id}: '
                         f'{len(self.monitored_jobs)} jobs left')
            self._push_result()
            self._update_progress()
        return 0
