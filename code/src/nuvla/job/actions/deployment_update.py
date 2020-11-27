# -*- coding: utf-8 -*-

import logging

from nuvla.connector import (connector_factory,
                             docker_connector,
                             docker_cli_connector,
                             docker_compose_cli_connector,
                             kubernetes_cli_connector)
from nuvla.api.resources import Deployment
from ..actions import action
from .deployment_start import DeploymentBase, get_env

action_name = 'update_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentUpdateJob(DeploymentBase):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def get_update_params_docker_service(self, deployment, registries_auth):
        module_content = Deployment.module_content(deployment)
        kwargs = {'sname'          : Deployment.uuid(deployment),
                  'image'          : module_content['image'],
                  'registries_auth': registries_auth}
        return kwargs

    def get_update_params_docker_stack(self, deployment, registries_auth):
        module_content = Deployment.module_content(deployment)
        kwargs = {'env'            : get_env(deployment),
                  'files'          : module_content.get('files'),
                  'stack_name'     : Deployment.uuid(deployment),
                  'docker_compose' : module_content['docker-compose'],
                  'registries_auth': registries_auth}
        return kwargs

    def get_update_params_docker_compose(self, deployment, registries_auth):
        return self.get_update_params_docker_stack(deployment, registries_auth)

    def get_update_params_kubernetes(self, deployment, registries_auth):
        return self.get_update_params_docker_stack(deployment, registries_auth)


    @staticmethod
    def get_connector_name(deployment):
        if Deployment.is_component(deployment):
            return 'docker'
        elif Deployment.is_application(deployment):
            is_compose = Deployment.is_compatibility_docker_compose(deployment)
            return 'docker_compose' if is_compose else 'docker_stack'
        elif Deployment.is_application_kubernetes(deployment):
            return 'kubernetes'


    @staticmethod
    def get_connector_class(connector_name):
        return {
            'docker'        : docker_connector,
            'docker_stack'  : docker_cli_connector,
            'docker_compose': docker_compose_cli_connector,
            'kubernetes'    : kubernetes_cli_connector
        }[connector_name]


    def update_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job update_deployment started for {}.'.format(deployment_id))
        self.job.set_progress(10)

        deployment      = self.api_dpl.get(deployment_id).data
        credential_id   = Deployment.credential_id(deployment)
        connector_name  = self.get_connector_name(deployment)
        connector_class = self.get_connector_class(connector_name)
        registries_auth = self.private_registries_auth(deployment)
        self.job.set_progress(20)

        connector = connector_factory(connector_class, self.api, credential_id)

        kwargs = {
            'docker'        : self.get_update_params_docker_service,
            'docker_stack'  : self.get_update_params_docker_stack,
            'docker_compose': self.get_update_params_docker_compose,
            'kubernetes'    : self.get_update_params_kubernetes
        }[connector_name](deployment, registries_auth)

        result = connector.update(**kwargs)

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(result)
        if ports_mapping:
            self.api_dpl.update_port_parameters(deployment, ports_mapping)

        self.api_dpl.set_state_started(deployment_id)

        return 0


    def do_work(self):
        return self.update_deployment()
