# -*- coding: utf-8 -*-

import logging
from abc import abstractmethod
from ...util import mapv


class DeploymentSetRemove(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.dep_set_id = self.job['target-resource']['href']

    def _deployments_to_remove(self):
        filter_deployment_set = f'deployment-set="{self.dep_set_id}"'
        deployments = self.api.search('deployment', filter=filter_deployment_set, select='id').resources
        deployments_ids = [deployment.id for deployment in deployments]
        logging.info(f'{self.dep_set_id} - Deployments to remove: {deployments_ids}')
        return deployments_ids

    @abstractmethod
    def _delete(self, deployment_id):
        pass

    def _remove_deployment(self, deployment_id):
        try:
            self._delete(deployment_id)
            logging.info(f'Deployment removed: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to remove {deployment_id}: {repr(ex)}')

    def do_work(self):
        logging.info(f'Start bulk deployment set remove {self.job.id}')
        mapv(self._remove_deployment, self._deployments_to_remove())
        logging.info(f'End of bulk deployment set apply remove {self.job.id}')
        return 0
