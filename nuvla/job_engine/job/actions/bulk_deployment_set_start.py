# -*- coding: utf-8 -*-

from ..actions import action
from .utils.bulk_deployment_set_apply import BulkDeploymentSetApply


@action('bulk_deployment_set_start')
class BulkDeploymentSetUpdateJob(BulkDeploymentSetApply):

    def __init__(self, job):
        super().__init__(job)
        self.action_name = 'start'
