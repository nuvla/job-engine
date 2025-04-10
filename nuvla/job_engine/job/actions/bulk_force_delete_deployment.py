# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob

action_name = 'bulk_force_delete_deployment'

@action(action_name)
class DeploymentBulkForceDeleteJob(DeploymentBulkJob):

    def __init__(self, job):
        super().__init__(job, action_name)

    def deployment_action(self, resource):
        return self.user_api.operation(resource,
                                       'force-delete', {'low-priority': True,
                                                        'parent-job': self.job.id})
