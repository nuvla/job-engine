# -*- coding: utf-8 -*-

import json
import logging
from ..actions import action
from ..job import JOB_QUEUED, JOB_RUNNING, JOB_SUCCESS, JOB_FAILED, JOB_CANCELED
from nuvla.api.util.filter import filter_and

action_name = 'monitor_bulk_job'

log = logging.getLogger(action_name)


@action(action_name)
class MonitorBulkJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.bulk_job_id = None
        self.bulk_job = None
        self.progress = 20
        self.jobs_in_progress = None
        self.jobs_done = None
        self.result = None

    def is_expired(self):
        filter_1d_old = 'created>"now-1d"'
        filter_job_id = f'id="{self.bulk_job_id}"'
        filter_str = filter_and([filter_job_id, filter_1d_old])
        return self.api.search('job', filter=filter_str, last=0).count == 0

    def reload_result(self):
        try:
            return json.loads(self.bulk_job.data.get('status-message'))
        except Exception:
            return {'bootstrap-exceptions': {},
                    'FAILED': [],
                    'SUCCESS': []}

    def query_jobs(self, states):
        filter_parent = f'parent-job="{self.bulk_job_id}"'
        filter_states = f'state={states}'
        filter_str = filter_and([filter_parent, filter_states])
        return self.api.search('job', filter=filter_str,
                               select='id, target-resource, state').resources

    def update_progress(self):
        count_done = len(self.jobs_done)
        count_in_progress = len(self.jobs_in_progress)
        total_count = count_done + len(self.jobs_in_progress)
        logging.info(f'{action_name} {self.bulk_job_id}: '
                     f'{count_in_progress} jobs left over {total_count}')
        progress_left = (100 - self.progress)
        if total_count > 0:
            progress_increment = progress_left / total_count
            self.progress += int(count_done * progress_increment)
        else:
            self.progress += progress_left

    def update_result(self):
        for job in self.jobs_done:
            resource_id = job.data['target-resource']['href']
            state = job.data['state']
            if state == JOB_SUCCESS and resource_id not in self.result['SUCCESS']:
                self.result['SUCCESS'].append(resource_id)
            if state == JOB_FAILED and resource_id not in self.result['FAILED']:
                self.result['FAILED'].append(resource_id)

    def build_update_job_body(self):
        update_job_body = {'progress': self.progress,
                           'status-message': json.dumps(self.result)}
        if self.progress == 100:
            update_job_body['state'] = JOB_SUCCESS
            update_job_body['return-code'] = 0
        return update_job_body

    def monitor(self):
        self.result = self.reload_result()
        self.jobs_done = self.query_jobs([JOB_FAILED, JOB_SUCCESS, JOB_CANCELED])
        self.jobs_in_progress = self.query_jobs([JOB_QUEUED, JOB_RUNNING])
        self.update_progress()
        self.update_result()
        self.api.edit(self.bulk_job_id, self.build_update_job_body())

    def do_work(self):
        log.info(f'Job started for {action_name} for job id {self.job.id}.')
        self.job.set_progress(10)
        self.bulk_job_id = self.job['target-resource']['href']
        self.bulk_job = self.api.get(self.bulk_job_id)
        if self.is_expired():
            self.api.operation(self.bulk_job, 'cancel')
        else:
            self.monitor()
        return 0
