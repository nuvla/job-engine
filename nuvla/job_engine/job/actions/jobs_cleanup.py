# -*- coding: utf-8 -*-

from ..job import JOB_FAILED, JOB_SUCCESS, JOB_CANCELED
from ..actions import action
from nuvla.api.api import Api as Nuvla

import logging


@action('cleanup_jobs')
class JobsCleanupJob(object):

    def __init__(self, job):
        self.job = job
        self.nuvla: Nuvla = self.job.api

    def cleanup_jobs(self):
        logging.info('Cleanup of completed jobs started.')

        days_back = 7
        filter_str = f"state=['{JOB_SUCCESS}', '{JOB_FAILED}', '{JOB_CANCELED}'] " \
                     f"and created<'now-{days_back}d'"
        ret = self.nuvla.delete_bulk('job', filter_str)
        if ret.data['timed_out']:
            msg = f'Cleanup of completed jobs have some failures: {ret.data}.'
            logging.warning(msg)
            self.job.set_status_message(msg)
        else:
            msg = f"Cleanup of completed jobs finished. Removed {ret.data['deleted']} jobs."
            logging.info(msg)
            self.job.set_status_message(msg)

        return 0

    def do_work(self):
        return self.cleanup_jobs()
