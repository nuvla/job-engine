# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob

action_name = 'bulk_delete_deployment'

@action(action_name)
class DeploymentBulkDeleteJob(DeploymentBulkJob):

    def __init__(self, job):
        super().__init__(job, action_name)

    def deployment_action(self, resource):
        return self.user_api.delete(resource.id)
