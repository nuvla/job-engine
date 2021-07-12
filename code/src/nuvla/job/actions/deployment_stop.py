# -*- coding: utf-8 -*-

import logging

from ...connector import docker_connector, docker_cli_connector, \
    docker_compose_cli_connector, kubernetes_cli_connector
from nuvla.api import NuvlaError, ConnectionError
from nuvla.api.resources import Deployment, Credential
from .deployment_start import DeploymentBase, initialize_connector
from ..util import override
from ..actions import action

action_name = 'stop_deployment'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentStopJob(DeploymentBase):

    def try_delete_deployment_credentials(self, deployment_id):
        cred_api = Credential(self.api, subtype='dummy')
        credentials = cred_api.find_parent(deployment_id)
        for credential in credentials:
            try:
                cred_api.delete(Credential.id(credential))
            except (NuvlaError, ConnectionError):
                pass

    def stop_component(self):
        deployment_id = Deployment.id(self.deployment)

        connector = initialize_connector(docker_connector, self.job, self.deployment)
        filter_params = 'parent="{}" and name="service-id"'.format(deployment_id)

        deployment_params = self.api.search('deployment-parameter', filter=filter_params,
                                            select='node-id,name,value').resources

        if len(deployment_params) > 0:
            service_id = deployment_params[0].data.get('value')
            if service_id is not None:
                connector.stop(service_id=service_id)
            else:
                self.job.set_status_message("Deployment parameter {} doesn't have a value!"
                                            .format(deployment_params[0].data.get('id')))
        else:
            self.job.set_status_message('No deployment parameters with service ID found!')

    def stop_application(self):
        if Deployment.is_compatibility_docker_compose(self.deployment):
            connector = initialize_connector(docker_compose_cli_connector, self.job, self.deployment)
        else:
            connector = initialize_connector(docker_cli_connector, self.job, self.deployment)

        result = connector.stop(stack_name=Deployment.uuid(self.deployment),
                                docker_compose=Deployment.module_content(self.deployment)[
                                    'docker-compose'])

        self.job.set_status_message(result)

    def stop_application_kubernetes(self):
        connector = initialize_connector(kubernetes_cli_connector, self.job, self.deployment)

        result = connector.stop(stack_name=Deployment.uuid(self.deployment))

        self.job.set_status_message(result)

    @override
    def handle_deployment(self, deployment: dict):
        if Deployment.is_component(self.deployment):
            self.stop_component()
        elif Deployment.is_application(self.deployment):
            self.stop_application()
        elif Deployment.is_application_kubernetes(self.deployment):
            self.stop_application_kubernetes()

    def stop_deployment(self):
        log.info('Job started for {}.'.format(self.deployment_id))

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.try_delete_deployment_credentials(self.deployment_id)

        self.api_dpl.set_state_stopped(self.deployment_id)

        return 0

    def do_work(self):
        return self.stop_deployment()
