# -*- coding: utf-8 -*-

from __future__ import print_function

from ..util import create_connector_instance, from_data_uuid

from ..actions import action

import logging


@action('start_deployment')
class DeploymentStartJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

        self._api_deployment = None
        self._module = None
        self._cloud_name = None
        self._api_connector = None
        self._api_configuration_nuvla = None
        self._api_user = None
        self._user_params = None
        self._connector_name = None
        self._connector_instance = None
        self.deployment_owner = self.api_deployment['acl']['owner']['principal']

    @property
    def connector_instance(self):
        if self._connector_instance is None:
            self._connector_instance = create_connector_instance(self.api_connector, self.api_credential)
        return self._connector_instance

    @property
    def api_deployment(self):
        if self._api_deployment is None:
            self._api_deployment = self.api.get(self.job['targetResource']['href']).data
        return self._api_deployment

    @property
    def api_configuration_nuvla(self):
        if self._api_configuration_nuvla is None:
            self._api_configuration_nuvla = self.api.get('configuration/slipstream').data
        return self._api_configuration_nuvla

    @property
    def user(self):
        if self._api_user is None:
            self._api_user = self.api.get('user/{}'.format(self.deployment_owner)).data
        return self._api_user

    def create_deployment_parameter(self, user, param_name, param_value=None, node_id=None, param_description=None):
        parameter = {'name': param_name,
                     'deployment': {'href': self.api_deployment['id']},
                     'acl': {'owner': {'principal': 'ADMIN',
                                       'type': 'ROLE'},
                             'rules': [{'principal': user,
                                        'type': 'USER',
                                        'right': 'MODIFY'}]}}  # TODO not always allow modification
        if node_id:
            parameter['nodeID'] = node_id
        if param_description:
            parameter['description'] = param_description
        if param_value:
            parameter['value'] = param_value
        return self.api.add('deploymentParameters', parameter)

    def __contruct_deployment_param_href(self, node_id, param_name):
        param_id = ':'.join(item or '' for item in [self.api_deployment['id'], node_id, param_name])
        return 'deployment-parameter/' + from_data_uuid(param_id)

    def set_deployment_parameter(self, param_name, param_value, node_id=None):
        deployment_parameter_href = self.__contruct_deployment_param_href(node_id, param_name)
        self.api.edit(deployment_parameter_href, {'value': param_value})

    @staticmethod
    def get_node_parameters(module):
        all_module_params_merged = {}
        local_module = module
        while local_module:
            params = local_module.get('outputParameters', []) + local_module.get('inputParameters', [])
            for param in params:
                param_name = param['parameter']
                if param_name in all_module_params_merged:
                    param.update(all_module_params_merged[param_name])
                all_module_params_merged[param_name] = param
            local_module = local_module.get('parent', {}).get('content', None)
        return all_module_params_merged

    @staticmethod
    def get_port_name_value(port_mapping):
        port_details = port_mapping.split(':')
        return '.'.join([port_details[0], port_details[2]]), port_details[1]

    def create_deployment_parameters(self, node_name, node_params, ports):
        # Global service params
        deployment_owner = self.api_deployment['acl']['owner']['principal']
        for param in self.api_deployment['outputParameters']:
            self.create_deployment_parameter(user=deployment_owner,
                                             param_name=param['parameter'],
                                             param_value=param.get('value'),
                                             node_id=None,
                                             param_description=param['description'])

        for param in node_params:
            self.create_deployment_parameter(user=deployment_owner,
                                             param_name=param['parameter'],
                                             param_value=param.get('value'),
                                             node_id=node_name,
                                             param_description=param['description'])

        for port_mapping in ports:
            port_param_name, _ = self.get_port_name_value(port_mapping)
            self.create_deployment_parameter(user=deployment_owner,
                                             param_name=port_param_name,
                                             node_id=node_name,
                                             param_description='Published port')
        self.create_deployment_parameter(user=deployment_owner,
                                         param_name='tcp.22',
                                         node_id=node_name,
                                         param_description='Published port')

    def handle_deployment(self):
        node_instance_name = 'machine'  # FIXME
        module_content = self.api_deployment['module'].get('content', {})

        cpu = module_content.get('cpu')  # FIXME
        ram = module_content.get('ram')
        disk = module_content.get('disk')
        network_type = module_content.get('networkType')
        login_user = module_content.get('loginUser')
        ports = module_content.get('ports', [])
        mounts = module_content.get('mounts', [])

        node_params = self.get_node_parameters(module_content)

        self.create_deployment_parameters(node_instance_name, node_params.values(), ports)

        cloud_credential_id = node_params['credential.id'].get('value')
        if cloud_credential_id is None:
            raise ValueError("Credential is not set!")

        vm = self.connector_instance.start(self.api_deployment)

        self.set_deployment_parameter(param_name='instanceid',
                                      param_value=self.connector_instance.extract_vm_id(vm),
                                      node_id=node_instance_name)

        self.set_deployment_parameter(param_name='hostname',
                                      param_value=self.connector_instance.extract_vm_ip(vm),
                                      node_id=node_instance_name)

        ports_mapping = self.connector_instance.extract_vm_ports_mapping(vm)
        if ports_mapping:
            for port_mapping in ports_mapping.split():
                port_param_name, port_param_value = self.get_port_name_value(port_mapping)
                self.set_deployment_parameter(param_name=port_param_name,
                                              param_value=port_param_value,
                                              node_id=node_instance_name)

        self.api.edit(self.api_deployment['id'], {'state': 'STARTED'})

        return 0

    def start_deployment(self):
        logging.info('Deployment start job started for {}.'.format(self.api_deployment.get('id')))

        self.job.set_progress(10)

        try:
            self.handle_deployment()
        except:
            self.api.edit(self.api_deployment['id'], {'state': 'ERROR'})
            raise

        return 10000

    def do_work(self):
        self.start_deployment()
