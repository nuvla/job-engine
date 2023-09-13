# -*- coding: utf-8 -*-

from ..actions import action
from .utils.bulk_deployment_set_apply import BulkDeploymentSetApply


@action('bulk_deployment_set_update')
class BulkDeploymentSetUpdateJob(BulkDeploymentSetApply):

    def __init__(self, _, job):
        super().__init__(_, job)
        self.action_name = 'update'
