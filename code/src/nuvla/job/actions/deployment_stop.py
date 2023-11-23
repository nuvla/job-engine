# -*- coding: utf-8 -*-

import logging

from ...connector import docker_service
from nuvla.api import NuvlaError, ConnectionError
from nuvla.api.resources import Deployment, Credential
from .utils.deployment_utils import (DeploymentBase,
                                     get_connector_class,
                                     get_connector_name,
                                     get_env,
                                     initialize_connector)
from ..util import override
from ..actions import action

action_name = 'stop_deployment'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentStopJob(DeploymentBase):

    def __init__(self, _, job):
        super().__init__(_, job, log)

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

        connector = initialize_connector(docker_service, self.job, self.deployment)
        filter_params = 'parent="{}" and name="service-id"'.format(deployment_id)

        deployment_params = self.api.search('deployment-parameter', filter=filter_params,
                                            select='id,node-id,name,value').resources

        if len(deployment_params) > 0:
            service_id = deployment_params[0].data.get('value')
            if service_id is not None:
                connector.stop(service_id=service_id,
                               env=get_env(self.deployment))
            else:
                self.job.set_status_message("Deployment parameter {} doesn't have a value!"
                                            .format(deployment_params[0].data.get('id')))
        else:
            self.job.set_status_message('No deployment parameters with service ID found!')

    def stop_application(self):
        env  = get_env(self.deployment.data)
        name = Deployment.uuid(self.deployment)
        connector_name  = get_connector_name(self.deployment)
        connector_class = get_connector_class(connector_name)
        connector = initialize_connector(connector_class, self.job, self.deployment)
        docker_compose = Deployment.module_content(self.deployment)['docker-compose']

        result = connector.stop(name=name, env=env, docker_compose=docker_compose)

        self.job.set_status_message(result)

    @override
    def handle_deployment(self):
        if Deployment.is_component(self.deployment):
            self.stop_component()
        else:
            self.stop_application()

    def stop_deployment(self):
        log.info('Job started for {}.'.format(self.deployment_id))

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.try_delete_deployment_credentials(self.deployment_id)

        self.api_dpl.set_state_stopped(self.deployment_id)

        return 0

    def do_work(self):
        return self.stop_deployment()
