# -*- coding: utf-8 -*-

import logging
from nuvla.api.util.filter import filter_and
from ..actions import action
from .utils.bulk_action import BulkAction


@action('bulk_deployment_set_stop')
class BulkDeploymentSetStopJob(BulkAction):

    def __init__(self, job):
        super().__init__(job)
        self.dep_set_id = self.job['target-resource']['href']

    def get_todo(self):
        filter_deployment_set = f'deployment-set="{self.dep_set_id}"'
        filter_state = f'state={["PENDING", "STARTING", "UPDATING", "STARTED", "ERROR"]}'
        filter_str = filter_and([filter_deployment_set, filter_state])
        deployments = self.user_api.search('deployment', filter=filter_str, select='id').resources
        return [deployment.id for deployment in deployments]

    def _stop_deployment(self, deployment_id):
        deployment = self.user_api.get(deployment_id)
        return self.user_api.operation(deployment, 'stop',
                                       {'low-priority': True,
                                        'parent-job': self.job.id})

    def action(self, deployment_id):
        return self._stop_deployment(deployment_id)

    def do_work(self):
        logging.info(f'Start bulk deployment set stop {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment set apply stop {self.job.id}')
