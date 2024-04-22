# -*- coding: utf-8 -*-

import re
import copy
import logging

from abc import abstractmethod

from nuvla.api import Api
from nuvla.api.resources import Deployment, DeploymentParameter
from nuvla.api.resources.base import ResourceNotFound

from ....connector import (docker_service,
                           docker_stack,
                           docker_compose,
                           kubernetes,
                           utils)
from ....connector.k8s_driver import get_kubernetes_local_endpoint


def get_connector_name(deployment):
    if Deployment.is_component(deployment):
        return 'docker_service'

    elif Deployment.is_application(deployment):
        is_compose = Deployment.is_compatibility_docker_compose(deployment)
        return 'docker_compose' if is_compose else 'docker_stack'

    elif Deployment.is_application_kubernetes(deployment):
        return 'kubernetes'

    subtype = Deployment.subtype(deployment)
    raise ValueError(f'Unsupported deployment subtype "{subtype}"')


def get_connector_class(connector_name):
    return {
        'docker_service': docker_service,
        'docker_stack':   docker_stack,
        'docker_compose': docker_compose,
        'kubernetes':     kubernetes
    }[connector_name]


def get_from_context(job, resource_id):
    try:
        return job.context[resource_id]
    except KeyError:
        raise KeyError(f'{resource_id} not found in job context')


def initialize_connector(connector_class, job, deployment):
    credential_id = Deployment.credential_id(deployment)
    credential = get_from_context(job, credential_id)
    infrastructure_service = copy.deepcopy(get_from_context(job, credential['parent']))
    infrastructure_service_type = infrastructure_service.get('subtype', '')

    # if you uncomment this, the pull-mode deployment_* will only work with the
    # NB compute-api. Which means standalone ISs and k8s capable NuvlaBoxes,
    # are not supported
    if job.is_in_pull_mode:
        if infrastructure_service_type == 'swarm':
            infrastructure_service['endpoint'] = None if connector_class is not docker_service \
                                                 else 'https://compute-api:5000'
        elif infrastructure_service_type == 'kubernetes':
            endpoint = get_kubernetes_local_endpoint()
            if endpoint:
                infrastructure_service['endpoint'] = endpoint
    else:
        # Not in pull mode (mixed or push) but endpoint is local
        endpoint = infrastructure_service['endpoint']
        if utils.is_endpoint_local(endpoint):
            raise RuntimeError(f'Endpoint is local ({endpoint}) so only "pull" mode is supported')

    return connector_class.instantiate_from_cimi(infrastructure_service, credential)


def get_env(deployment: dict):
    env_variables = {
        'NUVLA_DEPLOYMENT_UUID': deployment['id'].split('/')[-1],
        'NUVLA_DEPLOYMENT_ID': deployment['id'],
        'NUVLA_API_KEY': deployment['api-credentials']['api-key'],
        'NUVLA_API_SECRET': deployment['api-credentials']['api-secret'],
        'NUVLA_ENDPOINT': deployment['api-endpoint']}
    deployment_group_id = deployment.get('deployment-set')
    if deployment_group_id:
        env_variables['NUVLA_DEPLOYMENT_GROUP_ID'] = deployment_group_id
        env_variables['NUVLA_DEPLOYMENT_GROUP_UUID'] = deployment_group_id.split('/')[-1]

    module_content = Deployment.module_content(deployment)

    for env_var in module_content.get('environmental-variables', []):
        env_variables[env_var['name']] = env_var.get('value')

    return env_variables


class DeploymentBase(object):

    def __init__(self, _, job, log=None):
        self.log = log if log else logging.getLogger(self.__class__.__name__)
        self.job = job
        self.api = job.api
        self.deployment_id = self.job['target-resource']['href']
        self.api_dpl = self.get_deployment_api(self.deployment_id)
        self.deployment = self.api_dpl.get(self.deployment_id)

    def get_from_context(self, resource_id):
        return get_from_context(self.job, resource_id)

    def get_nuvlaedge_id(self):
        return self.deployment.data.get('nuvlabox')

    def get_nuvlaedge(self, nuvlaedge_id=None):
        if not nuvlaedge_id:
            nuvlaedge_id = self.get_nuvlaedge_id()
        return self.get_from_context(nuvlaedge_id)

    def get_nuvlaedge_status(self, nuvlaedge_id=None):
        ne_status_id = self.get_nuvlaedge(nuvlaedge_id)['nuvlabox-status']
        return self.get_from_context(ne_status_id)

    def get_hostname(self):
        try:
            if self.get_nuvlaedge_id():
                return self.get_nuvlaedge_status()['ip']
        except Exception as e:
            self.log.error(f'Failed to get hostname/ip from NuvlaEdge: {e}')

        credential_id = Deployment.credential_id(self.deployment)
        credential = self.get_from_context(credential_id)
        endpoint = self.get_from_context(credential['parent'])['endpoint']
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', endpoint).group('host')

    def get_nuvlaedge_ips(self):
        try:
            if self.get_nuvlaedge_id():
                return self.get_nuvlaedge_status()['network']['ips']
        except Exception as e:
            self.log.error(f'Failed to get ips from NuvlaEdge: {e}')
        return {}

    def get_deployment_api(self, deployment_id) -> Deployment:
        creds = Deployment._get_attr(Deployment(self.api).get(deployment_id),
                                     'api-credentials')
        insecure = not self.api.session.verify
        api = Api(endpoint=self.api.endpoint, insecure=insecure,
                  persist_cookie=False, reauthenticate=True)
        api.login_apikey(creds['api-key'], creds['api-secret'])
        return Deployment(api)

    def private_registries_auth(self):
        registries_credentials = self.deployment.data.get('registries-credentials')
        if registries_credentials:
            list_cred_infra = []
            for registry_cred in registries_credentials:
                credential = self.job.context[registry_cred]
                infra_service = self.job.context[credential['parent']]
                registry_auth = {'username': credential['username'],
                                 'password': credential['password'],
                                 'serveraddress': infra_service[
                                     'endpoint'].replace('https://', '')}
                list_cred_infra.append(registry_auth)
            return list_cred_infra
        else:
            return None

    def create_deployment_parameter(self, deployment_id, user_id,
                                    param_name, param_value=None,
                                    node_id=None, param_description=None):
        return self.create_update_deployment_parameter(deployment_id, user_id,
                                                       param_name, param_value,
                                                       node_id, param_description,
                                                       update=False)

    def create_update_deployment_parameter(self, deployment_id, user_id,
                                           param_name, param_value=None,
                                           node_id=None, param_description=None,
                                           update=True):
        try:
            param = self.api_dpl._get_parameter(deployment_id, param_name, node_id)
            if update and param and param_value:
                # self.api_dpl.set_parameter(deployment_id, node_id, param_name, param_value)
                self.api_dpl.nuvla.edit(param.id, {'value': param_value})
        except ResourceNotFound:
            self.api_dpl.create_parameter(deployment_id,
                                          user_id, param_name, param_value,
                                          node_id, param_description)

    def application_params_update(self, services):
        if services:
            for service in services:
                node_id = service['node-id']
                for key, value in service.items():
                    param_name = f'{node_id}.{key}'
                    try:
                        self.api_dpl.set_parameter_create_if_needed(
                            Deployment.id(self.deployment),
                            Deployment.owner(self.deployment),
                            param_name,
                            param_value=value,
                            node_id=node_id)
                    except Exception as e:
                        self.log.error(f'Failed to set output parameter "{param_name}" with value "{value}": {e}')

    def create_update_ips_output_parameters(self):
        ips = self.get_nuvlaedge_ips()
        if not ips:
            return
        for name, ip in ips.items():
            param_name = f'ip.{name}'
            try:
                self.api_dpl.set_parameter_create_if_needed(
                    Deployment.id(self.deployment),
                    Deployment.owner(self.deployment),
                    param_name,
                    param_value=ip)
            except Exception as e:
                self.log.error(f'Failed to set output parameter "{param_name}" with value "{ip}": {e}')

    def create_update_hostname_output_parameter(self):
        self.create_update_deployment_parameter(
            deployment_id=Deployment.id(self.deployment),
            user_id=Deployment.owner(self.deployment),
            param_name=DeploymentParameter.HOSTNAME['name'],
            param_description=DeploymentParameter.HOSTNAME['description'],
            param_value=self.get_hostname())

    def create_user_output_params(self):
        deployment_id = Deployment.id(self.deployment)
        deployment_owner = Deployment.owner(self.deployment)

        self.create_update_hostname_output_parameter()
        self.create_update_ips_output_parameters()

        module_content = Deployment.module_content(self.deployment)
        for output_param in module_content.get('output-parameters', []):
            self.create_deployment_parameter(
                deployment_id=deployment_id,
                user_id=deployment_owner,
                param_name=output_param['name'],
                param_description=output_param.get('description'))

    @abstractmethod
    def handle_deployment(self):
        pass

    def try_handle_raise_exception(self):
        try:
            return self.handle_deployment()
        except Exception as ex:
            self.log.error(f"Failed to {self.job['action']} {self.deployment_id}: {ex}")
            try:
                self.job.set_status_message(repr(ex))
                if self.job.get('execution-mode', '').lower() != 'mixed':
                    self.api_dpl.set_state_error(self.deployment_id)
            except Exception as ex_state:
                self.log.error(f'Failed to set error state for {self.deployment_id}: {ex_state}')

            raise ex
