# -*- coding: utf-8 -*-

import logging

from .nuvla import Deployment, DeploymentParameter
from nuvla.connector import connector_factory, docker_connector, docker_cli_connector
from ..actions import action

action_name = 'start_deployment'

log = logging.getLogger(action_name)


def get_env(deployment):
    env_variables = {'NUVLA_DEPLOYMENT_ID': deployment['id'],
                     'NUVLA_API_KEY': deployment['api-credentials']['api-key'],
                     'NUVLA_API_SECRET': deployment['api-credentials']['api-secret'],
                     'NUVLA_ENDPOINT': deployment['api-endpoint']}

    module_content = Deployment.module_content(deployment)

    for env_var in module_content.get('environmental-variables', []):
        env_variables[env_var['name']] = env_var.get('value')

    return env_variables


def application_params_update(api_dpl, deployment, services):
    if services:
        for service in services:
            node_id = service['node-id']
            for key, value in service.items():
                api_dpl.set_parameter_create_if_needed(
                    resource_id=Deployment.id(deployment),
                    user_id=Deployment.owner(deployment),
                    node_id=node_id,
                    param_name='{}.{}'.format(node_id, key),
                    param_value=value)


@action(action_name)
class DeploymentStartJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def create_deployment_parameter(self, deployment_id, user_id, param_name,
                                    param_value=None, node_id=None, param_description=None):
        return self.api_dpl.create_parameter(deployment_id, user_id, param_name,
                                             param_value, node_id, param_description)

    def create_user_output_params(self, deployment):
        module_content = Deployment.module_content(deployment)
        for output_param in module_content.get('output-parameters', []):
            self.create_deployment_parameter(deployment_id=Deployment.id(deployment),
                                             user_id=Deployment.owner(deployment),
                                             param_name=output_param['name'],
                                             param_description=output_param.get('description'))

    def start_component(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))

        deployment_id = Deployment.id(deployment)
        node_instance_name = self.api_dpl.uuid(deployment)
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
                    param_description="mapping for {} port {}".format(protocol, str(target_port)),
                    node_id=node_instance_name)

        service = connector.start(service_name=node_instance_name,
                                  image=module_content['image'],
                                  env=get_env(deployment),
                                  mounts_opt=module_content.get('mounts'),
                                  ports_opt=module_ports,
                                  cpu_ratio=module_content.get('cpus'),
                                  memory=module_content.get('memory'),
                                  restart_policy_condition=restart_policy.get('condition'),
                                  restart_policy_delay=restart_policy.get('delay'),
                                  restart_policy_max_attempts=restart_policy.get('max-attempts'),
                                  restart_policy_window=restart_policy.get('window'))

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.SERVICE_ID['name'],
            param_value=connector.extract_vm_id(service),
            param_description=DeploymentParameter.SERVICE_ID['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.HOSTNAME['name'],
            param_value=connector.extract_vm_ip(service),
            param_description=DeploymentParameter.HOSTNAME['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.CURRENT_DESIRED['name'],
            param_value="",
            param_description=DeploymentParameter.CURRENT_DESIRED['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.CURRENT_STATE['name'],
            param_value="",
            param_description=DeploymentParameter.CURRENT_STATE['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.CURRENT_ERROR['name'],
            param_value="",
            param_description=DeploymentParameter.CURRENT_ERROR['description'],
            node_id=node_instance_name)

        # FIXME: get number of desired replicas of Replicated service from deployment. 1 for now.
        desired = 1
        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.REPLICAS_DESIRED['name'],
            param_value=str(desired),
            param_description=DeploymentParameter.REPLICAS_DESIRED['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.REPLICAS_RUNNING['name'],
            param_value="0",
            param_description=DeploymentParameter.REPLICAS_RUNNING['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.RESTART_EXIT_CODE['name'],
            param_value="",
            param_description=DeploymentParameter.RESTART_EXIT_CODE['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.RESTART_ERR_MSG['name'],
            param_value="",
            param_description=DeploymentParameter.RESTART_ERR_MSG['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.RESTART_TIMESTAMP['name'],
            param_value="",
            param_description=DeploymentParameter.RESTART_TIMESTAMP['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.RESTART_NUMBER['name'],
            param_value="",
            param_description=DeploymentParameter.RESTART_NUMBER['description'],
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.CHECK_TIMESTAMP['name'],
            param_value="",
            param_description=DeploymentParameter.CHECK_TIMESTAMP['description'],
            node_id=node_instance_name)

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(service)
        self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def start_application(self, deployment):
        deployment_id = Deployment.id(deployment)

        connector = connector_factory(docker_cli_connector, self.api, deployment.get('parent'))

        module_content = Deployment.module_content(deployment)

        deployment_owner = Deployment.owner(deployment)

        docker_compose = module_content['docker-compose']

        result, services = connector.start(docker_compose=docker_compose,
                                           stack_name=Deployment.uuid(deployment),
                                           env=get_env(deployment),
                                           files=module_content.get('files'))

        self.job.set_status_message(result.stdout.decode('UTF-8'))

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.HOSTNAME['name'],
            param_value=connector.extract_vm_ip(services),
            param_description=DeploymentParameter.HOSTNAME['description'])

        application_params_update(self.api_dpl, deployment, services)

    def handle_deployment(self, deployment):

        if Deployment.is_component(deployment):
            self.start_component(deployment)
        elif Deployment.is_application(deployment):
            self.start_application(deployment)

        self.create_user_output_params(deployment)

    def start_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], deployment_id, ex))
            try:
                self.job.set_status_message(repr(ex))
                self.api_dpl.set_state_error(deployment_id)
            except Exception as ex_state:
                log.error('Failed to set error state for {0}: {1}'.format(deployment_id, ex_state))

            raise ex

        self.api_dpl.set_state_started(deployment_id)

        return 0

    def do_work(self):
        return self.start_deployment()
