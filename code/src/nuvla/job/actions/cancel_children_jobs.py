# -*- coding: utf-8 -*-

from ..job import JOB_RUNNING, JOB_QUEUED
from ..actions import action
from nuvla.api.api import Api as Nuvla
from nuvla.api.util.filter import filter_or, filter_and

import logging


@action('cancel_children_jobs')
class CancelChildrenJobsJob(object):

    def __init__(self, _, job):
        self.job = job
        self.nuvla: Nuvla = self.job.api

    def _running_children_jobs(self, parent_job):
        if parent_job:
            filter_children = f'parent-job="{parent_job}"'
            filter_state = filter_or([f"state='{JOB_RUNNING}'",
                                      f"state='{JOB_QUEUED}'"])
            filter_str = filter_and([filter_children, filter_state])
            return self.nuvla.search('job', filter=filter_str, select='id')
        else:
            return []

    def _try_cancel(self, job):
        try:
            self.nuvla.operation(job, 'cancel')
            return True
        except Exception as ex:
            logging.error(f'Unable to cancel following {job.id}: {repr(ex)}')
            return False

    def do_work(self):
        parent_job = self.job['target-resource']['href']
        cancel_result = []
        for job in self._running_children_jobs(parent_job):
            cancel_result.append(self._try_cancel(job))
        return 0 if all(cancel_result) else 1
