# -*- coding: utf-8 -*-

import json
import logging
from ..actions import action

action_name = 'bulk_jobs_monitor'

log = logging.getLogger(action_name)


@action(action_name)
class HandleTrialEnd(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def _build_monitored_jobs_filter(self):
        filter_jobs_ids = ' or '.join(map(lambda job: f'id="{job}"', self.monitored_jobs))
        filter_finished_jobs = 'progress=100'
        return f'({filter_jobs_ids}) and {filter_finished_jobs}'

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

    def get_monitored_jobs(self, bulk_job_id):
        pass


    def do_work(self):
        log.info(f'Job started for {action_name} for job id {self.job.id}.')
        self.job.set_progress(10)
        bulk_job_id = self.job['target-resource']['href']
        bulk_job = self.api.get(bulk_job_id).data
        # aggregate jobs, RUNNING, SUCCESS, FAILED, QUEUED
        # job_timedout();
        #   when running for > 1d, cancel job, return 0


        count_jobs = 0
        count_completed_jobs = 0
        count_running_jobs = 0
        monitored_jobs = self.get_monitored_jobs(bulk_job_id)
        progress_increment = len(count_jobs) / 80
        logging.info(f'{action} {bulk_job_id}: '
                     f'{count_running_jobs} jobs left')
        self._push_result() # to bulk_job
        self._update_progress() # to bulk_job

        self.job.set_status_message()
        return 0
