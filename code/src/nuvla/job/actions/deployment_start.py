# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from .deployment import Deployment, DeploymentParameter
from ..actions import action

action_name = 'start_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentStartJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    @staticmethod
    def get_port_name_value(port_mapping):
        port_details = port_mapping.split(':')
        return '.'.join([port_details[0], port_details[2]]), port_details[1]

    def create_deployment_parameter(self, deployment_id, user_id, param_name,
                                    param_value=None, node_id=None, param_description=None):
        return self.api_dpl.create_parameter(deployment_id, user_id, param_name,
                                             param_value, node_id, param_description)

    def handle_deployment(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('credential-id'))

        deployment_id = deployment['id']
        node_instance_name = self.api_dpl.uuid(deployment_id)
        deployment_owner = deployment['acl']['owners'][0]

        container_env = ['NUVLA_DEPLOYMENT_ID={}'.format(deployment_id),
                         'NUVLA_API_KEY={}'.format(deployment['api-credentials']['api-key']),
                         'NUVLA_API_SECRET={}'.format(deployment['api-credentials']['api-secret']),
                         'NUVLA_ENDPOINT={}'.format(deployment['api-endpoint'])]

        for env_var in deployment['module']['content'].get('environmental-variables', []):
            env_var_name = env_var['name']
            env_var_value = env_var.get('value')
            if env_var_value is not None:
                env_var_def = "{}='{}'".format(env_var_name, env_var_value)
                container_env.append(env_var_def)

        service = connector.start(service_name=node_instance_name,
                                  image=deployment['module']['content']['image'],
                                  env=container_env,
                                  mounts_opt=deployment['module']['content'].get('mounts'),
                                  ports_opt=deployment['module']['content'].get('ports'))

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

        ports_mapping = connector.extract_vm_ports_mapping(service)
        if ports_mapping:
            for port_mapping in ports_mapping.split():
                port_param_name, port_param_value = self.get_port_name_value(port_mapping)
                self.create_deployment_parameter(
                    deployment_id=deployment_id,
                    user_id=deployment_owner,
                    param_name=port_param_name,
                    param_value=port_param_value,
                    node_id=node_instance_name)

        for output_param in deployment['module']['content'].get('output-parameters', []):
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
                self.api_dpl.set_state_error(deployment_id)
            except Exception as ex:
                log.error('Failed to set error state for {0}: {1}'.format(deployment_id, ex))
                raise ex

        self.api_dpl.set_state_started(deployment_id)

    def do_work(self):
        self.start_deployment()
        return 0
