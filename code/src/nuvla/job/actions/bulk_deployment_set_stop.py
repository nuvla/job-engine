# -*- coding: utf-8 -*-

import logging
from nuvla.api.util.filter import filter_or, filter_and
from ..actions import action
from ..util import mapv


@action('bulk_deployment_set_stop')
class BulkDeploymentSetStopJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.user_api = job.get_user_api()
        self.dep_set_id = self.job['target-resource']['href']

    def _deployments_to_stop(self):
        filter_deployment_set = f'deployment-set={self.dep_set_id}'
        filter_state = filter_or(["state='PENDING'",
                                  "state='STARTING'",
                                  "state='UPDATING'",
                                  "state='STARTED'",
                                  "state='ERROR'"])
        filter_str = filter_and([filter_deployment_set, filter_state])
        deployments = self.user_api.search('deployment', filter=filter_str, select='id').resources
        return [deployment.id for deployment in deployments]

    def _stop_deployment(self, deployment_id):
        try:
            deployment = self.user_api.get(deployment_id)
            self.user_api.operation(deployment, 'stop')
            logging.info(f'Deployment stopped: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to stop {deployment_id}: {repr(ex)}')

    def do_work(self):
        logging.info(f'Start bulk deployment set stop {self.job.id}')
        mapv(self._stop_deployment, self._deployments_to_stop())
        logging.info(f'End of bulk deployment set apply stop {self.job.id}')
