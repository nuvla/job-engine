# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('bulk_delete_deployment')
class DeploymentBulkDeleteJob(DeploymentBulkJob):

    def __init__(self, job):
        super().__init__(job)

    def deployment_action(self, resource):
        return self.user_api.delete(resource.id)

    def do_work(self):
        logging.info(f'Start bulk deployment delete {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment delete {self.job.id}')
