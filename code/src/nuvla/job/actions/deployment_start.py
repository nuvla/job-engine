# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from .nuvla import Deployment, DeploymentParameter
from ..actions import action

action_name = 'start_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentStartJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def create_deployment_parameter(self, deployment_id, user_id, param_name,
                                    param_value=None, node_id=None, param_description=None):
        return self.api_dpl.create_parameter(deployment_id, user_id, param_name,
                                             param_value, node_id, param_description)

    def handle_deployment(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))

        deployment_id = deployment['id']
        node_instance_name = self.api_dpl.uuid(deployment_id)
        deployment_owner = deployment['acl']['owners'][0]
        module_content = deployment['module']['content']

        container_env = ['NUVLA_DEPLOYMENT_ID={}'.format(deployment_id),
                         'NUVLA_API_KEY={}'.format(deployment['api-credentials']['api-key']),
                         'NUVLA_API_SECRET={}'.format(deployment['api-credentials']['api-secret']),
                         'NUVLA_ENDPOINT={}'.format(deployment['api-endpoint'])]

        for env_var in module_content.get('environmental-variables', []):
            env_var_name = env_var['name']
            env_var_value = env_var.get('value')
            if env_var_value is not None:
                env_var_def = "{}={}".format(env_var_name, env_var_value)
                container_env.append(env_var_def)

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
                                  env=container_env,
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
        self.api_dpl.update_port_parameters(deployment_id, ports_mapping)

        for output_param in module_content.get('output-parameters', []):
            self.create_deployment_parameter(deployment_id=deployment_id,
                                             user_id=deployment_owner,
                                             param_name=output_param['name'],
                                             param_description=output_param.get('description'),
                                             node_id=node_instance_name)

    def start_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            log.error('Failed to start deployment {0}: {1}'.format(deployment_id, ex))
            try:
                self.job.set_status_message(str(ex))
                self.api_dpl.set_state_error(deployment_id)
                return 1
            except Exception as ex:
                log.error('Failed to set error state for {0}: {1}'.format(deployment_id, ex))
                raise ex

        self.api_dpl.set_state_started(deployment_id)

    def do_work(self):
        return_code = self.start_deployment()
        return return_code or 0
