# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('start_deployment_set')
class DeploymentSetStartJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)
        self.log_message = 'Deployment set'

    def action_deployment(self, deployment):
        response = self.user_api.operation(deployment, 'start',
                                           {'low-priority': True})
        return response.data['location']

    def do_work(self):
        logging.info(f'Start deployment set start {self.job.id}')
        result = self.run()
        deployment_set_id = self.job['target-resource']['href']
        self.user_api.edit(deployment_set_id, {'state': 'STARTED'})
        logging.info(f'End of deployment set start {self.job.id}')
        return result
