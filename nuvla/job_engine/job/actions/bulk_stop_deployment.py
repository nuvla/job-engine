# -*- coding: utf-8 -*-

import logging
from ..actions import action
from .utils.bulk_deployment import DeploymentBulkJob

action_name = 'bulk_stop_deployment'

@action(action_name)
class DeploymentBulkStopJob(DeploymentBulkJob):

    def __init__(self, job):
        super().__init__(job, action_name)

    def deployment_action(self, deployment):
        return self.user_api.operation(deployment,
                                       'stop',
                                       {'low-priority': True,
                                        'parent-job': self.job.id})
