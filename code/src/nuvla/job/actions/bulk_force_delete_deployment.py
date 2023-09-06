# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('bulk_force_delete_deployment')
class DeploymentBulkForceDeleteJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)

    def action_deployment(self, deployment):
        self.user_api.operation(deployment, 'force-delete', {'low-priority': True})

    def do_work(self):
        logging.info(f'Start bulk deployment force delete {self.job.id}')
        result = self.run('force delete')
        logging.info(f'End of bulk deployment force delete {self.job.id}')
        return result
