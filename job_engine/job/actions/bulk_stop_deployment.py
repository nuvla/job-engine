# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('bulk_stop_deployment')
class DeploymentBulkStopJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)

    def deployment_action(self, deployment):
        self.user_api.operation(deployment,
                                'stop',
                                {'low-priority': True,
                                 'parent-job': self.job.id})

    def do_work(self):
        logging.info(f'Start bulk deployment stop {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment stop {self.job.id}')
