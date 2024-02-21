# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('bulk_update_deployment')
class DeploymentBulkUpdateJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)

    def deployment_action(self, deployment):
        module_href = self.job.payload.get('module-href')
        if module_href:
            self.user_api.operation(deployment,
                                    'fetch-module',
                                    {'module-href': module_href})
        self.user_api.operation(deployment, 'update', {'low-priority': True,
                                                       'parent-job': self.job.id})

    def do_work(self):
        logging.info(f'Start bulk deployment update {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment update {self.job.id}')
