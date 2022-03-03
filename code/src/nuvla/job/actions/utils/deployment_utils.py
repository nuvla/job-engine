# -*- coding: utf-8 -*-

import re
import copy
from abc import abstractmethod
from nuvla.api import Api
from nuvla.api.resources import Deployment
from nuvla.api.resources.base import ResourceNotFound
from ....connector import docker_service, docker_stack, docker_compose, \
    kubernetes


def get_connector_name(deployment):
    if Deployment.is_component(deployment):
        return 'docker_service'
    elif Deployment.is_application(deployment):
        is_compose = Deployment.is_compatibility_docker_compose(deployment)
        return 'docker_compose' if is_compose else 'docker_stack'
    elif Deployment.is_application_kubernetes(deployment):
        return 'kubernetes'


def get_connector_class(connector_name):
    return {
        'docker_service': docker_service,
        'docker_stack'  : docker_stack,
        'docker_compose': docker_compose,
        'kubernetes'    : kubernetes
    }[connector_name]


def get_from_context(job, resource_id):
    try:
        return job.context[resource_id]
    except KeyError:
        raise KeyError(f'{resource_id} not found in job context')


def initialize_connector(connector_class, job, deployment):
    credential_id = Deployment.credential_id(deployment)
    credential = get_from_context(job, credential_id)
    infrastructure_service = copy.deepcopy(
        get_from_context(job, credential['parent']))
    # if you uncomment this, the pull-mode deployment_* will only work with the
    # NB compute-api. Which means standalone ISs and k8s capable NuvlaBoxes,
    # are not supported
    if job.is_in_pull_mode and \
            infrastructure_service.get('subtype', '') == 'swarm':
        infrastructure_service['endpoint'] = 'https://compute-api:5000'
    return connector_class.instantiate_from_cimi(
        infrastructure_service, credential)


def get_env(deployment: dict):
    env_variables = {
        'NUVLA_DEPLOYMENT_UUID': deployment['id'].split('/')[-1],
        'NUVLA_DEPLOYMENT_ID': deployment['id'],
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
                    Deployment.id(deployment),
                    Deployment.owner(deployment),
                    f'{node_id}.{key}', param_value=value, node_id=node_id)


class DeploymentBase(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.deployment_id = self.job['target-resource']['href']
        self.api_dpl = self.get_deployment_api(self.deployment_id)
        self.deployment = self.api_dpl.get(self.deployment_id)

    def get_from_context(self, resource_id):
        return get_from_context(self.job, resource_id)

    def get_hostname(self):
        credential_id = Deployment.credential_id(self.deployment)
        credential = self.get_from_context(credential_id)
        endpoint = self.get_from_context(credential['parent'])['endpoint']
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', endpoint).group(
            'host')

    def get_deployment_api(self, deployment_id):
        creds = Deployment._get_attr(Deployment(self.api).get(deployment_id),
                                     'api-credentials')
        insecure = not self.api.session.verify
        api = Api(endpoint=self.api.endpoint, insecure=insecure,
                  persist_cookie=False, reauthenticate=True)
        api.login_apikey(creds['api-key'], creds['api-secret'])
        return Deployment(api)

    def private_registries_auth(self, deployment):
        registries_credentials = deployment.get('registries-credentials')
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
        try:
            self.api_dpl._get_parameter(deployment_id, param_name, node_id)
        except ResourceNotFound:
            self.api_dpl.create_parameter(deployment_id,
                                          user_id, param_name, param_value,
                                          node_id, param_description)

    def create_user_output_params(self, deployment):
        module_content = Deployment.module_content(deployment)
        for output_param in module_content.get('output-parameters', []):
            self.create_deployment_parameter(
                deployment_id=Deployment.id(deployment),
                user_id=Deployment.owner(deployment),
                param_name=output_param['name'],
                param_description=output_param.get('description'))

    @abstractmethod
    def handle_deployment(self):
        pass

    def try_handle_raise_exception(self, log):
        try:
            return self.handle_deployment()
        except Exception as ex:
            log.error(
                f"Failed to {self.job['action']} {self.deployment_id}: {ex}")
            try:
                self.job.set_status_message(repr(ex))
                if self.job.get('execution-mode', '').lower() != 'pull':
                    self.api_dpl.set_state_error(self.deployment_id)
            except Exception as ex_state:
                log.error(
                    f'Failed to set error state for {self.deployment_id}: {ex_state}')

            raise ex
