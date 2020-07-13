# -*- coding: utf-8 -*-

from ..actions import action

import logging


@action('cleanup_jobs')
class JobsCleanupJob(object):

    def __init__(self, _, job):
        self.job = job
        self.nuvla = self.job.api

    def cleanup_jobs(self):
        logging.info('Cleanup of completed jobs started.')

        days_back = 7
        filter = f"(state='SUCCESS' or state='FAILED') and created<'now-{days_back}d'"
        ret = self.nuvla.delete_bulk(index='job', filter=filter)
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
