# -*- coding: utf-8 -*-
# FIXME: this should go to nuvla.api library.


class ResourceNotFound(Exception):
    pass


class ResourceCreateError(Exception):
    def __init__(self, reason, response=None):
        super(ResourceCreateError, self).__init__(reason)
        self.reason = reason
        self.response = response


def check_created(resp, errmsg=''):
    """
    Returns id of the created resource or raises ResourceCreateError.
    :param resp: nuvla.api.models.CimiResponse
    :param errmsg: error message
    :return: str, resource id
    """
    if resp.data['status'] == 201:
        return resp.data['resource-id']
    else:
        if errmsg:
            msg = '{0} : {1}'.format(errmsg, resp.data['message'])
        else:
            msg = resp.data['message']
        raise ResourceCreateError(msg, resp)


class Deployment(object):
    """Stateless interface to Nuvla module deployment."""

    STATE_STARTED = 'STARTED'
    STATE_STOPPED = 'STOPPED'
    STATE_ERROR = 'ERROR'

    resource = 'deployment'

    @staticmethod
    def id(deployment):
        return deployment['id']

    @staticmethod
    def uuid(deployment):
        return Deployment.id(deployment).split('/')[1]

    @staticmethod
    def subtype(deployment):
        return Deployment.module(deployment)['subtype']

    @staticmethod
    def is_component(deployment):
        return Deployment.subtype(deployment) == 'component'

    @staticmethod
    def is_application(deployment):
        return Deployment.subtype(deployment) == 'application'

    @staticmethod
    def is_application_kubernetes(deployment):
        return Deployment.subtype(deployment) == 'application_kubernetes'

    @staticmethod
    def module(deployment):
        return deployment['module']

    @staticmethod
    def module_content(deployment):
        return Deployment.module(deployment)['content']

    @staticmethod
    def owner(deployment):
        return deployment['acl']['owners'][0]

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

        res = self.nuvla.add(self.resource, module)
        deployment_id = check_created(res, 'Failed to create deployment.')

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

    def set_parameter(self, resource_id, node_id, name, value):
        if not isinstance(value, str):
            raise ValueError('Parameter value should be string.')
        param = self._get_parameter(resource_id, node_id, name, select='id')
        return self.nuvla.edit(param.id, {'value': value})

    def set_parameter_ignoring_errors(self, resource_id, node_id, name, value):
        try:
            self.set_parameter(resource_id, node_id, name, value)
        except Exception as _:
            pass

    def set_parameter_create_if_needed(self, resource_id, user_id, param_name, param_value=None,
                                       node_id=None, param_description=None):
        try:
            self.set_parameter(resource_id, node_id, param_name, param_value)
        except ResourceNotFound as _:
            self.create_parameter(resource_id, user_id, param_name, param_value,
                                  node_id, param_description)

    def _get_parameter(self, resource_id, node_id, name, select=None):
        filters = "parent='{0}' and node-id='{1}' and name='{2}'".format(resource_id, node_id, name)
        res = self.nuvla.search("deployment-parameter", filter=filters, select=select)
        if res.count < 1:
            raise ResourceNotFound('Deployment parameter "{0}" not found.'.format(filters))
        return res.resources[0]

    def get_parameter(self, resource_id, node_id, name):
        try:
            param = self._get_parameter(resource_id, node_id, name)
        except ResourceNotFound:
            return None
        return param.data.get('value')

    def update_port_parameters(self, deployment, ports_mapping):
        if ports_mapping:
            for port_mapping in ports_mapping.split():
                port_param_name, port_param_value = self.get_port_name_value(port_mapping)
                self.set_parameter(Deployment.id(deployment), Deployment.uuid(deployment),
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

    CURRENT_DESIRED = {'name': 'current.desired.state',
                       'description': "Desired state of the container's current task."}

    CURRENT_STATE = {'name': 'current.state',
                     'description': "Actual state of the container's current task."}

    CURRENT_ERROR = {'name': 'current.error.message',
                     'description': "Error message (if any) of the container's current task."}

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


class Callback:

    resource = 'callback'

    def __init__(self, nuvla):
        self.nuvla = nuvla

    def create(self, action_name, target_resource, data=None, expires=None, acl=None):
        """
        :param action_name: name of the action
        :param target_resource: resource id
        :param data: dict
        :param expires: ISO timestamp
        :param acl: acl
        :return:
        """

        callback = {"action": action_name,
                    "target-resource": {'href': target_resource}}

        if data:
            callback.update({"data": data})
        if expires:
            callback.update({"expires": expires})
        if acl:
            callback.update({"acl": acl})

        resource_id = check_created(self.nuvla.add(self.resource, callback),
                                    'Failed to create callback.')
        return resource_id


class Notification:

    resource = 'notification'

    def __init__(self, nuvla):
        self.nuvla = nuvla

    def create(self, message, category, content_unique_id,
               target_resource=None, not_before=None, expiry=None,
               callback_id=None, callback_msg=None, acl=None):

        notification = {'message': message,
                        'category': category,
                        'content-unique-id': content_unique_id}

        if target_resource:
            notification.update({'target-resource': target_resource})
        if not_before:
            notification.update({'not-before': not_before})
        if expiry:
            notification.update({'expiry': expiry})
        if callback_id:
            notification.update({'callback': callback_id})
        if callback_msg:
            notification.update({'callback-msg': callback_msg})
        if acl:
            notification.update({'acl': acl})

        return check_created(self.nuvla.add(self.resource, notification),
                             'Failed to create notification.')

    def find_by_content_unique_id(self, content_unique_id):
        resp = self.nuvla.search(self.resource,
                                 filter="content-unique-id='{}'".format(content_unique_id))
        if resp.count < 1:
            return None
        else:
            return list(resp.resources)[0]

    def exists_with_content_unique_id(self, content_unique_id):
        return self.find_by_content_unique_id(content_unique_id) is not None


class Module:

    resource = 'module'

    def __init__(self, nuvla):
        self.nuvla = nuvla

    def find(self, **kvargs):
        return self.nuvla.search(self.resource, **kvargs)

    def get(self, resource_id):
        """
        Returns module identified by `resource_id` as dictionary.
        :param resource_id: str
        :return: dict
        """
        return self.nuvla.get(resource_id).data
