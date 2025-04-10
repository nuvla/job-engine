# -*- coding: utf-8 -*-

import logging
from nuvla.api.util.filter import filter_and
from ..actions import action
from .utils.bulk_action import BulkAction
from .utils.bulk_deployment_set_apply import EdgeResolver, get_dg_api, get_dg_owner_api

action_name = 'bulk_deployment_set_stop'

@action(action_name)
class BulkDeploymentSetStopJob(BulkAction):

    def __init__(self, job):
        super().__init__(job, action_name)
        self.dep_set_id = self.job['target-resource']['href']
        self.dg_owner_api = get_dg_owner_api(job)
        self.dg_api = get_dg_api(job)
        self.dep_set = self.dg_api.get(self.dep_set_id)
        self.edge_resolver = EdgeResolver(self.dg_owner_api, self.dep_set.data.get('subtype'))

    def get_todo(self):
        filter_deployment_set = f'deployment-set="{self.dep_set_id}"'
        filter_state = f'state={["PENDING", "STARTING", "UPDATING", "STARTED", "ERROR"]}'
        filter_str = filter_and([filter_deployment_set, filter_state])
        deployments = self.dg_api.search('deployment', filter=filter_str, select='id').resources
        return [deployment.id for deployment in deployments]

    def _stop_deployment(self, deployment_id):
        deployment = self.dg_api.get(deployment_id)
        nuvlabox_id = deployment.data.get('nuvlabox')
        if nuvlabox_id:
            self.edge_resolver.throw_edge_offline(nuvlabox_id)
        return self.dg_api.operation(deployment, 'stop',
                                     {'low-priority': True,
                                      'parent-job': self.job.id})

    def action(self, deployment_id):
        return self._stop_deployment(deployment_id)
