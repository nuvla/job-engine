# -*- coding: utf-8 -*-

from ..actions import action
from .utils.bulk_deployment_set_apply import BulkDeploymentSetApply

action_name = 'bulk_deployment_set_update'

@action('bulk_deployment_set_update')
class BulkDeploymentSetUpdateJob(BulkDeploymentSetApply):

    def __init__(self, job):
        super().__init__(job, action_name)
