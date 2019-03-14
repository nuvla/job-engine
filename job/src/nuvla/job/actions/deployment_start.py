# -*- coding: utf-8 -*-

from ..util import create_connector_instance

from ..actions import action

import logging
from math import ceil


@action('start_deployment')
class DeploymentStartJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

    def create_deployment_parameter(self, deployment_id, user, param_name, param_value=None, node_id=None,
                                    param_description=None):
        parameter = {'name': param_name,
                     'deployment': {'href': deployment_id},
                     'acl': {'owner': {'principal': 'ADMIN',
                                       'type': 'ROLE'},
                             'rules': [{'principal': user,
                                        'type': 'USER',
                                        'right': 'MODIFY'}]}}
        if node_id:
            parameter['node-id'] = node_id
        if param_description:
            parameter['description'] = param_description
        if param_value:
            parameter['value'] = param_value
        return self.api.add('deployment-parameter', parameter)

    @staticmethod
    def get_port_name_value(port_mapping):
        port_details = port_mapping.split(':')
        return '.'.join([port_details[0], port_details[2]]), port_details[1]

    def handle_deployment(self, api_deployment):
        deployment_id = api_deployment['id']
        node_instance_name = deployment_id.split('/')[1]
        credential_id = api_deployment['credential-id']
        if credential_id is None:
            raise ValueError("Credential id is not set!")

        infrastructure_service_id = api_deployment['infrastructure-service-id']
        if infrastructure_service_id is None:
            raise ValueError("Infrastructure service id is not set!")

        api_credential = self.api.get(credential_id).data

        api_infrastructure_service = self.api.get(infrastructure_service_id).data

        connector_instance = create_connector_instance(api_infrastructure_service, api_credential)

        container_env = ['NUVLA_DEPLOYMENT_ID={}'.format(deployment_id),
                         'NUVLA_API_KEY={}'.format(api_deployment['api-credentials']['api-key']),
                         'NUVLA_API_SECRET={}'.format(api_deployment['api-credentials']['api-secret']),
                         'NUVLA_ENDPOINT={}'.format(self.api.endpoint)]

        container = connector_instance.start(service_name=node_instance_name,
                                             image=api_deployment['module']['content']['image'],
                                             env=container_env,
                                             mounts_opt=api_deployment['module']['content'].get('mounts'),
                                             ports_opt=api_deployment['module']['content'].get('ports'))

        deployment_owner = api_deployment['acl']['owner']['principal']

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user=deployment_owner,
            param_name='instance-id',
            param_value=connector_instance.extract_vm_id(container),
            param_description='Instance ID',
            node_id=node_instance_name)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user=deployment_owner,
            param_name='hostname',
            param_value=connector_instance.extract_vm_ip(container),
            param_description='Hostname',
            node_id=node_instance_name)

        ports_mapping = connector_instance.extract_vm_ports_mapping(container)
        if ports_mapping:
            for port_mapping in ports_mapping.split():
                port_param_name, port_param_value = self.get_port_name_value(port_mapping)
                self.create_deployment_parameter(
                    deployment_id=deployment_id,
                    user=deployment_owner,
                    param_name=port_param_name,
                    param_value=port_param_value,
                    node_id=node_instance_name)

        for output_param in api_deployment['module']['content'].get('output-parameters', []):
            self.create_deployment_parameter(deployment_id=deployment_id,
                                             user=deployment_owner,
                                             param_name=output_param['name'],
                                             param_description=output_param.get('description'),
                                             node_id=node_instance_name)

        self.api.edit(api_deployment['id'], {'state': 'STARTED'})

        return 0

    def start_deployment(self):
        deployment_id = self.job['targetResource']['href']

        api_deployment = self.api.get(deployment_id).data

        logging.info('Deployment start job started for {}.'.format(deployment_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(api_deployment)
        except:
            self.api.edit(deployment_id, {'state': 'ERROR'})
            raise

        return 10000

    def do_work(self):
        self.start_deployment()
