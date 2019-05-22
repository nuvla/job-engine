# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory
from .deployment import DeploymentJob
from ..actions import action

action_name = 'stop_deployment'

log = logging.getLogger(action_name)

@action(action_name)
class DeploymentStopJob(DeploymentJob):
    def __init__(self, _, job):
        super().__init__(job)

    def handle_deployment(self, deployment):
        credential_id = deployment.get('credential-id')

        connector = connector_factory(self.api, credential_id)

        filter_params = 'deployment/href="{}" and name="instance-id"'.format(deployment['id'])

        deployment_params = self.api.search('deployment-parameter', filter=filter_params,
                                            select='node-id,name,value').resources

        if len(deployment_params) > 0:
            service_id = deployment_params[0].data.get('value')
            logging.info('Stopping service {} for {}.'.format(service_id, credential_id))
            if service_id is not None:
                connector.stop([service_id])
            else:
                self.job.set_status_message("Deployment parameter {} doesn't have a value!"
                                            .format(deployment_params[0].data.get('id')))
        else:
            self.job.set_status_message('No deployment parameters with containers ids found!')

    def stop_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            log.error('Failed to stop deployment {0}: {1}'.format(deployment_id, ex))
            self.api_dpl.set_state_error(deployment_id)
            raise

        self.api_dpl.set_state_stopped(deployment_id)

        return 0

    def do_work(self):
        self.stop_deployment()
