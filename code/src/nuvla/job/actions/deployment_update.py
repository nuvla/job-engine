# -*- coding: utf-8 -*-
import logging

from nuvla.api.resources import Deployment
from ..actions import action
from .utils.deployment_utils import (DeploymentBase,
                                     get_env,
                                     get_connector_class,
                                     get_connector_name,
                                     initialize_connector)

action_name = 'update_deployment'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentUpdateJob(DeploymentBase):

    def __init__(self, _, job):
        super().__init__(_, job, log)

    @staticmethod
    def get_update_params_docker_service(deployment, registries_auth):
        module_content = Deployment.module_content(deployment)
        restart_policy = module_content.get('restart-policy', {})
        module_ports   = module_content.get('ports')
        kwargs = {'name'           : Deployment.uuid(deployment),
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

    @staticmethod
    def get_update_params_docker_stack(deployment, registries_auth):
        module_content = Deployment.module_content(deployment)
        kwargs = {'env'            : get_env(deployment),
                  'files'          : module_content.get('files'),
                  'name'           : Deployment.uuid(deployment),
                  'docker_compose' : module_content['docker-compose'],
                  'registries_auth': registries_auth}
        return kwargs

    def get_update_params_docker_compose(self, deployment, registries_auth):
        return self.get_update_params_docker_stack(deployment, registries_auth)

    def get_update_params_kubernetes(self, deployment, registries_auth):
        return self.get_update_params_docker_stack(deployment, registries_auth)

    def handle_deployment(self):
        log.info('Job update_deployment started for {}.'.format(self.deployment_id))
        self.job.set_progress(10)

        deployment      = self.deployment.data
        connector_name  = get_connector_name(deployment)
        connector_class = get_connector_class(connector_name)
        registries_auth = self.private_registries_auth()
        connector       = initialize_connector(connector_class, self.job, self.deployment)

        self.create_user_output_params()

        self.job.set_progress(20)

        kwargs = {
            'docker_service': self.get_update_params_docker_service,
            'docker_stack'  : self.get_update_params_docker_stack,
            'docker_compose': self.get_update_params_docker_compose,
            'kubernetes'    : self.get_update_params_kubernetes
        }[connector_name](deployment, registries_auth)

        _, services = connector.update(**kwargs)
        self.job.set_progress(80)

        if connector_name == 'docker_service':
            # immediately update any port mappings that are already available
            ports_mapping = connector.extract_vm_ports_mapping(services[0])
            if ports_mapping:
                self.api_dpl.update_port_parameters(deployment, ports_mapping)
        else:
            self.application_params_update(services)

        self.api_dpl.set_state_started(self.deployment_id)
        return 0

    def do_work(self):
        return self.try_handle_raise_exception()
