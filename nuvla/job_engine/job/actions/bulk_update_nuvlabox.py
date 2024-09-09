# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_nuvlabox import NuvlaboxBulkJob


@action('bulk_update_nuvlabox')
class NuvlaboxBulkUpdateJob(NuvlaboxBulkJob):

    def __init__(self, job):
        super().__init__(job)

    def nuvlabox_action(self, nuvlabox):
        data = self.job.payload
        data['parent-job'] = self.job.id
        return self.user_api.operation(nuvlabox, 'update-nuvlabox', data)

    def do_work(self):
        logging.info(f'Start bulk nuvlabox update {self.job.id}')
        self.run()
        logging.info(f'End of bulk nuvlabox update {self.job.id}')
