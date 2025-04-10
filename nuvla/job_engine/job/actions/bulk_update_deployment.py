# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob

action_name = 'bulk_update_deployment'

@action(action_name)
class DeploymentBulkUpdateJob(DeploymentBulkJob):

    def __init__(self, job):
        super().__init__(job, action_name)

    def deployment_action(self, deployment):
        module_href = self.job.payload.get('module-href')
        if module_href:
            self.user_api.operation(deployment,
                                    'fetch-module',
                                    {'module-href': module_href})
        return self.user_api.operation(deployment, 'update', {'low-priority': True,
                                                              'parent-job': self.job.id})
