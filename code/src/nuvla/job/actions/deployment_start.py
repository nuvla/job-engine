# -*- coding: utf-8 -*-

import logging

from ..util import override
from ...connector import docker_service
from ..actions import action
from .utils.deployment_utils import (DeploymentBase,
                                     get_connector_name,
                                     get_connector_class,
                                     initialize_connector,
                                     get_env)

from nuvla.api.resources import Deployment, DeploymentParameter

action_name = 'start_deployment'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentStartJob(DeploymentBase):

    def __init__(self, _, job):
        super().__init__(_, job, log)

    def start_component(self, deployment: dict):
        connector = initialize_connector(docker_service, self.job, deployment)

        deployment_id = Deployment.id(deployment)
        node_instance_name = Deployment.uuid(deployment)
        deployment_owner = Deployment.owner(deployment)
        module_content = Deployment.module_content(deployment)

        restart_policy = module_content.get('restart-policy', {})

        # create deployment parameters (with empty values) for all port mappings
        module_ports = module_content.get('ports')
        for port in (module_ports or []):
            target_port = port.get('target-port')
            protocol = port.get('protocol', 'tcp')
            if target_port is not None:
                self.create_deployment_parameter(
                    deployment_id=deployment_id,
                    user_id=deployment_owner,
                    param_name="{}.{}".format(protocol, str(target_port)),
                    param_description="mapping for {} port {}".format(protocol,
                                                                      str(target_port)),
                    node_id=node_instance_name)

        registries_auth = self.private_registries_auth()

        _, service = connector.start(
            service_name=node_instance_name,
            image=module_content['image'],
            env=get_env(deployment),
            mounts_opt=module_content.get('mounts'),
            ports_opt=module_ports,
            cpu_ratio=module_content.get('cpus'),
            memory=module_content.get('memory'),
            restart_policy_condition=restart_policy.get('condition'),
            restart_policy_delay=restart_policy.get('delay'),
            restart_policy_max_attempts=restart_policy.get('max-attempts'),
            restart_policy_window=restart_policy.get('window'),
            registry_auth=registries_auth[0] if registries_auth else None)

        # FIXME: get number of desired replicas of Replicated service from deployment. 1 for now.
        desired = 1

        deployment_parameters = (
            (DeploymentParameter.SERVICE_ID, service['ID']),
            (DeploymentParameter.REPLICAS_DESIRED, str(desired)),
            (DeploymentParameter.REPLICAS_RUNNING, '0'),
            (DeploymentParameter.CURRENT_DESIRED, ''),
            (DeploymentParameter.CURRENT_STATE, ''),
            (DeploymentParameter.CURRENT_ERROR, ''),
            (DeploymentParameter.RESTART_EXIT_CODE, ''),
            (DeploymentParameter.RESTART_ERR_MSG, ''),
            (DeploymentParameter.RESTART_TIMESTAMP, ''),
            (DeploymentParameter.RESTART_NUMBER, ''),
            (DeploymentParameter.CHECK_TIMESTAMP, ''),
        )

        for deployment_parameter, value in deployment_parameters:
            self.create_deployment_parameter(
                param_name=deployment_parameter['name'],
                param_value=value,
                param_description=deployment_parameter['description'],
                deployment_id=deployment_id,
                node_id=node_instance_name,
                user_id=deployment_owner)

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(service)
        self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def start_application(self, deployment: dict):
        connector_name   = get_connector_name(deployment)
        connector_class  = get_connector_class(connector_name)
        connector        = initialize_connector(connector_class, self.job, deployment)
        module_content   = Deployment.module_content(deployment)
        registries_auth  = self.private_registries_auth()

        result, services = connector.start(
            name=Deployment.uuid(deployment),
            docker_compose=module_content['docker-compose'],
            env=get_env(deployment),
            files=module_content.get('files'),
            registries_auth=registries_auth)

        self.job.set_status_message(result)

        self.application_params_update(services)

    @override
    def handle_deployment(self):
        deployment = self.deployment.data

        self.create_user_output_params()

        if Deployment.is_component(self.deployment):
            self.start_component(deployment)
        else:
            self.start_application(deployment)

    def start_deployment(self):

        log.info('Job started for {}.'.format(self.deployment_id))

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.api_dpl.set_state_started(self.deployment_id)

        return 0

    def do_work(self):
        return self.start_deployment()
