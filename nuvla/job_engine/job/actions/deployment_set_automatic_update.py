# -*- coding: utf-8 -*-

from ..actions import action

import logging

@action('deployment_set_automatic_update')
class DeploymentSetAutomaticUpdateJob(object):

    def __init__(self, job):
        self.job = job
        self.api = job.api
        self.dep_set_id = self.job['target-resource']['href']

    def _auto_update(self):
        try:
            dep_set = self.api.get(self.dep_set_id)
            if dep_set.data['state'] in ['STARTED', 'UPDATED', 'PARTIALLY-STARTED', 'PARTIALLY-UPDATED']:
                self.api.operation(dep_set, 'auto-update')
                logging.info(f'Deployment set auto updated: {self.dep_set_id}')
        except Exception as ex:
            logging.error(f'Failed to auto update {self.dep_set_id}: {repr(ex)}')

    def do_work(self):
        logging.info(f'Deployment set automatic update {self.job.id}')
        self._auto_update()
        logging.info(f'End of deployment set automatic update {self.job.id}')
        return 0
