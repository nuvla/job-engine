# -*- coding: utf-8 -*-

import logging
from ..actions import action
from ..job import JOB_QUEUED, JOB_RUNNING, JOB_SUCCESS, JOB_FAILED, JOB_CANCELED
from ..actions.utils.bulk_action import BulkActionResult
from nuvla.api.util.filter import filter_and

action_name = 'monitor_bulk_job'

log = logging.getLogger(action_name)


@action(action_name)
class MonitorBulkJob(object):
    job_failed_reason = 'Job failed'
    job_canceled_reason = 'Job canceled'

    def __init__(self, job):
        self.job = job
        self.api = job.api
        self.bulk_job_id = self.job['target-resource']['href']
        self.bulk_job = self.api.get(self.bulk_job_id)
        self.progress = self.bulk_job.data.get('progress', 0)
        self.result = BulkActionResult.from_json(self.bulk_job.data.get('status-message'))
        child_jobs = self._query_jobs()
        self.jobs_by_state = self._group_child_job_by_state(child_jobs)
        self.jobs_count = len(child_jobs)
        self.jobs_in_progress = (self.jobs_by_state.get(JOB_RUNNING, [])
                                 + self.jobs_by_state.get(JOB_QUEUED, []))
        self.jobs_done = (self.jobs_by_state.get(JOB_SUCCESS, [])
                          + self.jobs_by_state.get(JOB_FAILED, [])
                          + self.jobs_by_state.get(JOB_CANCELED, []))

    def is_expired(self):
        filter_1d_old = 'created>"now-1h"'
        filter_job_id = f'id="{self.bulk_job_id}"'
        filter_str = filter_and([filter_job_id, filter_1d_old])
        return self.api.search('job', filter=filter_str, last=0).count == 0

    def _query_jobs(self):
        filter_parent = f'parent-job="{self.bulk_job_id}"'
        return self.api.search('job', filter=filter_parent, last=10000,
                               select='id, target-resource, state').resources

    @staticmethod
    def _group_child_job_by_state(child_jobs):
        grouped = {}
        for child_job in child_jobs:
            grouped.setdefault(child_job.data['state'], []).append(child_job)
        return grouped

    def update_progress(self):
        count_done = len(self.jobs_done)
        count_in_progress = len(self.jobs_in_progress)
        self.jobs_count = count_done + len(self.jobs_in_progress)
        logging.info(f'{action_name} {self.bulk_job_id}: '
                     f'{count_in_progress} jobs left over {self.jobs_count}')
        progress_left = (100 - self.progress)
        if self.jobs_count > 0:
            progress_increment = progress_left / self.jobs_count
            self.progress += int(count_done * progress_increment)
        else:
            self.progress += progress_left

    def update_result(self):
        self.result.set_queued_actions([j.id for j in self.jobs_by_state.get(JOB_QUEUED, [])])
        self.result.set_running_actions([j.id for j in self.jobs_by_state.get(JOB_RUNNING, [])])
        for job in self.jobs_done:
            resource_id = job.data['target-resource']['href']
            state = job.data['state']
            if state == JOB_SUCCESS and not self.result.exist_in_success(resource_id):
                self.result.add_success_action(resource_id)
            if state == JOB_FAILED and not self.result.exist_in_fail_reason_ids(
                    self.job_failed_reason, resource_id):
                self.result.fail_action(self.job_failed_reason, resource_id)
            if state == JOB_CANCELED and not self.result.exist_in_fail_reason_ids(
                    self.job_canceled_reason, resource_id):
                self.result.fail_action(self.job_canceled_reason, resource_id)

    def build_update_job_body(self):
        update_job_body = {'progress': self.progress,
                           'status-message': self.result.to_json()}
        if self.progress == 100:
            update_job_body['state'] = JOB_SUCCESS
            update_job_body['return-code'] = 0
        return update_job_body

    def monitor(self):
        self.update_progress()
        self.update_result()
        self.api.edit(self.bulk_job_id, self.build_update_job_body())

    def do_work(self):
        log.info(f'Job started for {action_name} for job id {self.job.id}.')
        self.job.set_progress(10)
        if self.is_expired():
            self.api.operation(self.bulk_job, 'cancel')
        else:
            self.monitor()
        return 0
