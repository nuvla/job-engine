# -*- coding: utf-8 -*-

class DeploymentJob(object):

    DPARAM_REPLICAS_DESIRED = {'name': 'replicas.desired',
                               'description': 'Desired number of replicas.'}
    DPARAM_REPLICAS_RUNNING = {'name': 'replicas.running',
                               'description': 'Number of running replicas.'}

    def __init__(self, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)


# FIXME: this should go to nuvla.api.deployment module.

class ResourceNotFound(Exception):
    pass


class Deployment():
    "Stateless interface to Nuvla module deployment."

    STATE_STARTED = 'STARTED'
    STATE_STOPPED = 'STOPPED'
    STATE_ERROR = 'ERROR'

    @staticmethod
    def uuid(resource_id):
        return resource_id.split('/')[1]

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
            deployment.update({"credential-id": infra_cred_id})
        try:
            return self.nuvla.edit(deployment_id, deployment).data
        except Exception as ex:
            raise Exception('ERROR: Failed to edit {0}: {1}'.format(deployment_id, ex))

    def set_infra_cred_id(self, resource_id, infra_cred_id):
        try:
            return self.nuvla.edit(resource_id, {"credential-id": infra_cred_id}).data
        except Exception as ex:
            raise Exception('ERROR: Failed to edit {0}: {1}'.format(resource_id, ex))

    def deployment_delete(self, resource_id):
        self.nuvla.delete(resource_id)

    def create_parameter(self, resource_id, user_id, param_name, param_value=None,
                         node_id=None, param_description=None):
        parameter = {'name': param_name,
                     'deployment': {'href': resource_id},
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
        filters = "deployment/href='{0}' and node-id='{1}' and name='{2}'".format(
            resource_id, node_name, name)
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


class Credential():

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
