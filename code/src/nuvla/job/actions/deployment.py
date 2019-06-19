# -*- coding: utf-8 -*-
# FIXME: this should go to nuvla.api.deployment module.


class ResourceNotFound(Exception):
    pass


class Deployment(object):
    """Stateless interface to Nuvla module deployment."""

    STATE_STARTED = 'STARTED'
    STATE_STOPPED = 'STOPPED'
    STATE_ERROR = 'ERROR'

    @staticmethod
    def uuid(resource_id):
        return resource_id.split('/')[1]

    @staticmethod
    def get_port_name_value(port_mapping):
        port_details = port_mapping.split(':')
        return '.'.join([port_details[0], port_details[2]]), port_details[1]

    def __init__(self, nuvla):
        self.nuvla = nuvla

    def get(self, resource_id):
        """
        Returns deployment identified by `resource_id` as dictionary.
        :param resource_id: str
        :return: dict
        """
        return self.nuvla.get(resource_id).data

    def create(self, module_id, infra_cred_id=None):
        """
        Returns deployment created from `module_id` as dictionary.
        Sets `infra_cred_id` infrastructure credentials on the deployment, if given.

        :param module_id: str, resource URI
        :param infra_cred_id: str, resource URI
        :return: dict
        """
        module = {"module": {"href": module_id}}

        res = self.nuvla.add('deployment', module)
        if res.data['status'] != 201:
            raise Exception('ERROR: Failed to create deployment.')
        deployment_id = res.data['resource-id']
        deployment = self.get(deployment_id)

        if infra_cred_id:
            deployment.update({'parent': infra_cred_id})
        try:
            return self.nuvla.edit(deployment_id, deployment).data
        except Exception as ex:
            raise Exception('ERROR: Failed to edit {0}: {1}'.format(deployment_id, ex))

    def set_infra_cred_id(self, resource_id, infra_cred_id):
        try:
            return self.nuvla.edit(resource_id, {'parent': infra_cred_id}).data
        except Exception as ex:
            raise Exception('ERROR: Failed to edit {0}: {1}'.format(resource_id, ex))

    def deployment_delete(self, resource_id):
        self.nuvla.delete(resource_id)

    def create_parameter(self, resource_id, user_id, param_name, param_value=None,
                         node_id=None, param_description=None):
        parameter = {'name': param_name,
                     'parent': resource_id,
                     'acl': {'owners': ['group/nuvla-admin'],
                             'edit-acl': [user_id]}}
        if node_id:
            parameter['node-id'] = node_id
        if param_description:
            parameter['description'] = param_description
        if param_value:
            parameter['value'] = param_value
        return self.nuvla.add('deployment-parameter', parameter)

    def set_parameter(self, resource_id, node_name, name, value):
        if not isinstance(value, str):
            raise ValueError('Parameter value should be string.')
        param = self._get_parameter(resource_id, node_name, name, select='id')
        return self.nuvla.edit(param.id, {'value': value})

    def _get_parameter(self, resource_id, node_name, name, select=None):
        filters = "parent='{0}' and node-id='{1}' and name='{2}'".format(resource_id, node_name, name)
        res = self.nuvla.search("deployment-parameter", filter=filters, select=select)
        if res.count < 1:
            raise ResourceNotFound('Deployment parameter "{0}" not found.'.format(filters))
        return res.resources[0]

    def get_parameter(self, resource_id, node_name, name):
        try:
            param = self._get_parameter(resource_id, node_name, name)
        except ResourceNotFound:
            return None
        return param.data.get('value')

    def update_port_parameters(self, deployment_id, ports_mapping):
        if ports_mapping:
            for port_mapping in ports_mapping.split():
                port_param_name, port_param_value = self.get_port_name_value(port_mapping)
                self.set_parameter(deployment_id, self.uuid(deployment_id),
                                   port_param_name, port_param_value)

    def set_state(self, resource_id, state):
        self.nuvla.edit(resource_id, {'state': state})

    def set_state_started(self, resource_id):
        self.set_state(resource_id, self.STATE_STARTED)

    def set_state_stopped(self, resource_id):
        self.set_state(resource_id, self.STATE_STOPPED)

    def set_state_error(self, resource_id):
        self.set_state(resource_id, self.STATE_ERROR)

    def delete(self, resource_id):
        self.nuvla.delete(resource_id)


class DeploymentParameter(object):
    REPLICAS_DESIRED = {'name': 'replicas.desired',
                        'description': 'Desired number of service replicas.'}

    REPLICAS_RUNNING = {'name': 'replicas.running',
                        'description': 'Number of running service replicas.'}

    CHECK_TIMESTAMP = {'name': 'check.timestamp',
                       'description': 'Service check timestamp.'}

    RESTART_NUMBER = {'name': 'restart.number',
                      'description': 'Total number of restarts of all containers due to failures.'}

    RESTART_ERR_MSG = {'name': 'restart.error.message',
                       'description': 'Error message of the last restarted container.'}

    RESTART_EXIT_CODE = {'name': 'restart.exit.code',
                         'description': 'Exit code of the last restarted container.'}

    RESTART_TIMESTAMP = {'name': 'restart.timestamp',
                         'description': 'Restart timestamp of the last restarted container.'}

    SERVICE_ID = {'name': 'service-id',
                  'description': 'Service ID.'}

    HOSTNAME = {'name': 'hostname',
                'description': 'Hostname or IP to access the service.'}


class Credential(object):

    def __init__(self, nuvla):
        self.nuvla = nuvla

    def find(self, infra_service_id):
        """
        Returns list of credentials for `infra_service_id` infrastructure service.
        :param infra_service_id: str, URI
        :return: list
        """
        filters = "parent='{}'".format(infra_service_id)
        creds = self.nuvla.search('credential', filter=filters, select="id")
        return creds.resources
