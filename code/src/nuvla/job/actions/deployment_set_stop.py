# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob


@action('stop_deployment_set')
class DeploymentSetStopJob(DeploymentBulkJob):

    def __init__(self, _, job):
        super().__init__(_, job)
        self.log_message = 'Deployment set'

    def action_deployment(self, deployment):
        response = self.user_api.operation(deployment, 'stop',
                                           {'low-priority': True})
        return response.data['location']

    def do_work(self):
        logging.info(f'Start deployment set stop {self.job.id}')
        result = self.run('stop')
        deployment_set_id = self.job['target-resource']['href']
        self.user_api.edit(deployment_set_id, {'state': 'STOPPED'})
        logging.info(f'End of deployment set stop {self.job.id}')
        return result
