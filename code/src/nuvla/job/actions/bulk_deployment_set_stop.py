# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment_set_apply import BulkDeploymentSetApply
from nuvla.api.util.filter import filter_or, filter_and


@action('bulk_deployment_set_stop')
class BulkDeploymentSetStopJob(BulkDeploymentSetApply):

    def __init__(self, _, job):
        super().__init__(_, job)
        self.action('stop')

    def _deployments_to_stop(self):
        filter_deployment_set = f'deployment-set={self.dep_set_id}'
        filter_state = filter_or(["state='PENDING'",
                                  "state='STARTING'",
                                  "state='UPDATING'",
                                  "state='STARTED'",
                                  "state='ERROR'"])
        filter_str = filter_and([filter_deployment_set, filter_state])
        deployments = self.user_api.search('deployment', filter=filter_str, select='id').resoruces
        return [deployment.id for deployment in deployments]

    def do_work(self):
        logging.info(f'Start bulk deployment set stop {self.job.id}')
        self._map(self._stop_deployment, self._deployments_to_stop())
        logging.info(f'End of bulk deployment set apply stop {self.job.id}')
