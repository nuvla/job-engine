# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('bulk_force_delete_deployment')
class DeploymentBulkForceDeleteJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)

    def deployment_action(self, resource):
        self.user_api.operation(resource,
                                'force-delete', {'low-priority': True,
                                                 'parent-job': self.job.id})

    def do_work(self):
        logging.info(f'Start bulk deployment force delete {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment force delete {self.job.id}')
