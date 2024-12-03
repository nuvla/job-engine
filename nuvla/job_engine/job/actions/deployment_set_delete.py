# -*- coding: utf-8 -*-

from .utils.deployment_set_remove import DeploymentSetRemove
from ..actions import action


@action('deployment_set_delete')
class DeploymentSetDeleteJob(DeploymentSetRemove):

    def __init__(self, job):
        super().__init__(job)

    def _delete(self, deployment_id):
        self.dg_owner_api.delete(deployment_id)
