# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_nuvlabox import NuvlaboxBulkJob


@action('bulk_update_nuvlabox')
class NuvlaboxBulkUpdateJob(NuvlaboxBulkJob):

    def __init__(self, job):
        super().__init__(job)

    def deployment_action(self, deployment):
        self.user_api.operation(deployment,
                                'stop',
                                {'parent-job': self.job.id})

    def do_work(self):
        logging.info(f'Start bulk nuvlabox update {self.job.id}')
        self.run()
        logging.info(f'End of bulk nuvlabox update {self.job.id}')
