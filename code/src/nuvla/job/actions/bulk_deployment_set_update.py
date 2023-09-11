# -*- coding: utf-8 -*-

from ..actions import action
from .bulk_deployment_set_start import BulkDeploymentSetStartJob


@action('bulk_deployment_set_update')
class BulkDeploymentSetUpdateJob(BulkDeploymentSetStartJob):

    def __init__(self, _, job):
        super().__init__(_, job)