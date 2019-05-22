# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory
from .deployment import DeploymentJob
from ..actions import action

action_name = 'deployment_state'

log = logging.getLogger(action_name)

@action(action_name)
class DeploymentStateJob(DeploymentJob):

    def __init__(self, _, job):
        super().__init__(job)

    def handle_deployment(self, deployment):
        connector = connector_factory(self.api, deployment.get('credential-id'))
        did = deployment['id']
        # FIXME: at the moment deployment UUID is the service name.
        sname = self.api_dpl.uuid(did)
        running, desired = connector.service_replicas_running(sname)
        self.api_dpl.set_parameter(did, sname, self.DPARAM_REPLICAS_DESIRED['name'], str(desired))
        self.api_dpl.set_parameter(did, sname, self.DPARAM_REPLICAS_RUNNING['name'], str(running))

    def do_work(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get_json(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            log.error('Failed to obtain deployment state {0}: {1}'.format(deployment_id, ex))
            raise

        return 10000
