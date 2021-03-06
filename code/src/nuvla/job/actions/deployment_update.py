# -*- coding: utf-8 -*-

import logging

from nuvla.connector import (connector_factory,
                             docker_connector,
                             docker_cli_connector,
                             docker_compose_cli_connector,
                             kubernetes_cli_connector)
from nuvla.api.resources import Deployment
from ..actions import action
from .deployment_start import (DeploymentBase,
                               application_params_update,
                               get_env)

action_name = 'update_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentUpdateJob(DeploymentBase):

    def __init__(self, _, job):
        super().__init__(job)

    def get_update_params_docker_service(self, deployment, registries_auth):
        module_content = Deployment.module_content(deployment)
        restart_policy = module_content.get('restart-policy', {})
        module_ports   = module_content.get('ports')
        kwargs = {'service_name'   : Deployment.uuid(deployment),
                  'env'            : get_env(deployment),
                  'image'          : module_content['image'],
                  'mounts_opt'     : module_content.get('mounts'),
                  'cpu_ratio'      : module_content.get('cpus'),
                  'memory'         : module_content.get('memory'),
                  'ports_opt'      : module_ports,
                  'registries_auth': registries_auth,
                  'restart_policy_condition'   : restart_policy.get('condition'),
                  'restart_policy_delay'       : restart_policy.get('delay'),
                  'restart_policy_max_attempts': restart_policy.get('max-attempts'),
                  'restart_policy_window'      : restart_policy.get('window')}
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
            return 'docker_service'
        elif Deployment.is_application(deployment):
            is_compose = Deployment.is_compatibility_docker_compose(deployment)
            return 'docker_compose' if is_compose else 'docker_stack'
        elif Deployment.is_application_kubernetes(deployment):
            return 'kubernetes'


    @staticmethod
    def get_connector_class(connector_name):
        return {
            'docker_service': docker_connector,
            'docker_stack'  : docker_cli_connector,
            'docker_compose': docker_compose_cli_connector,
            'kubernetes'    : kubernetes_cli_connector
        }[connector_name]


    def update_deployment(self, deployment_id):
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
            'docker_service': self.get_update_params_docker_service,
            'docker_stack'  : self.get_update_params_docker_stack,
            'docker_compose': self.get_update_params_docker_compose,
            'kubernetes'    : self.get_update_params_kubernetes
        }[connector_name](deployment, registries_auth)

        result, services = connector.update(**kwargs)
        self.job.set_progress(80)

        if connector_name == 'docker_service':
            # immediately update any port mappings that are already available
            ports_mapping = connector.extract_vm_ports_mapping(services[0])
            if ports_mapping:
                self.api_dpl.update_port_parameters(deployment, ports_mapping)
        else:
            application_params_update(self.api_dpl, deployment, services)
        self.create_user_output_params(deployment)

        self.api_dpl.set_state_started(deployment_id)
        return 0


    def do_work(self):
        deployment_id = self.job['target-resource']['href']
        try:
            return self.update_deployment(deployment_id)
        except Exception as e:
            self.api_dpl.set_state_error(deployment_id)
            raise
