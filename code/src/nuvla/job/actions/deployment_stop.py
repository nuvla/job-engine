# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from nuvla.api import NuvlaError, ConnectionError
from .deployment import Deployment
from ..actions import action

action_name = 'stop_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def try_delete_deployment_credentials(self, deployment_id):
        credentials = self.api.search('credential', filter="parent='{}'".format(deployment_id),
                                      select='id, parent').resources
        for credential in credentials:
            try:
                self.api.delete(credential.data['id'])
            except (NuvlaError, ConnectionError):
                pass

    def handle_deployment(self, deployment):
        deployment_id = deployment['id']

        credential_id = deployment.get('credential-id')

        connector = connector_factory(docker_connector, self.api, credential_id)

        filter_params = 'parent="{}" and name="service-id"'.format(deployment_id)

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
            self.job.set_status_message('No deployment parameters with service ID found!')

        self.try_delete_deployment_credentials(deployment_id)

    def stop_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            log.error('Failed to stop deployment {0}: {1}'.format(deployment_id, ex))
            try:
                self.job.set_status_message(str(ex))
                self.api_dpl.set_state_error(deployment_id)
                return 1
            except Exception as ex:
                log.error('Failed to set error state for {0}: {1}'.format(deployment_id, ex))
                raise ex

        self.api_dpl.set_state_stopped(deployment_id)

    def do_work(self):
        return_code = self.stop_deployment()
        return return_code or 0
