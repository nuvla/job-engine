# -*- coding: utf-8 -*-

import re
import copy
import datetime
import logging
from types import ModuleType
from typing import Union, List

from abc import abstractmethod, ABC

from nuvla.api import Api
from nuvla.api.models import CimiResource
from nuvla.api.resources import Deployment, DeploymentParameter
from nuvla.api.resources.base import ResourceNotFound

from ... import Job
from ...util import override
from ....connector import (docker_stack,
                           docker_compose,
                           kubernetes,
                           utils)
from ....connector.connector import ConnectorCOE
from ....connector.k8s_driver import get_kubernetes_local_endpoint
from ....connector.utils import LOCAL

CONNECTOR_KIND_HELM = 'helm'
APP_SUBTYPE_HELM = 'application_helm'


def get_connector_name(deployment: Union[dict, CimiResource]):
    if Deployment.is_application(deployment):
        is_compose = Deployment.is_compatibility_docker_compose(deployment)
        return 'docker_compose' if is_compose else 'docker_stack'

    elif Deployment.is_application_kubernetes(deployment):
        return 'kubernetes'

    elif Deployment.subtype(deployment) == APP_SUBTYPE_HELM:
        return CONNECTOR_KIND_HELM

    subtype = Deployment.subtype(deployment)
    raise ValueError(f'Unsupported deployment subtype "{subtype}"')


def get_connector_module(connector_name):
    match connector_name:
        case 'docker_stack':
            return docker_stack
        case 'docker_compose':
            return docker_compose
        case 'kubernetes' | 'helm':
            return kubernetes
        case _:
            raise ValueError(f'Unsupported connector name "{connector_name}"')


def get_from_context(job, resource_id):
    try:
        return job.context[resource_id]
    except KeyError:
        raise KeyError(f'{resource_id} not found in job context')


def update_infra_service_endpoint_for_pull_mode(infra_service):
    infra_service_type = infra_service.get('subtype', '')
    if infra_service_type == 'swarm':
        infra_service['endpoint'] = None
    elif infra_service_type == 'kubernetes':
        endpoint = get_kubernetes_local_endpoint()
        if not endpoint:
            infra_service_endpoint = infra_service.get('endpoint')
            if infra_service_endpoint and infra_service_endpoint != LOCAL:
                return
            raise ValueError('Kubernetes local endpoint not found in PULL mode.')
        infra_service['endpoint'] = endpoint
    else:
        logging.info(f'Not updating infra service endpoint for '
                     f'"{infra_service_type}" subtype.')


def initialize_connector(connector_module: ModuleType, job: Job,
                         deployment: Union[dict, CimiResource]):
    credential_id = Deployment.credential_id(deployment)
    credential = get_from_context(job, credential_id)
    infra_service = copy.deepcopy(get_from_context(job, credential['parent']))

    # Not in pull mode (i.e., either mixed or push) but endpoint is local.
    raise_not_pull_mode_on_local_infra_service(job, infra_service)

    if job.is_in_pull_mode:
        update_infra_service_endpoint_for_pull_mode(infra_service)

    # FIXME: this is a hack to make sure that the helm connector is used.
    if Deployment.subtype(deployment) == APP_SUBTYPE_HELM:
        infra_service['subtype'] = CONNECTOR_KIND_HELM

    return connector_module.instantiate_from_cimi(infra_service, credential,
                                                  job=job)


def raise_not_pull_mode_on_local_infra_service(job: Job, infra_service: dict):
    endpoint = infra_service['endpoint']
    not_pull_on_local_endpoint = (not job.is_in_pull_mode and
                                  utils.is_docker_endpoint_local(endpoint))
    if not_pull_on_local_endpoint:
        raise RuntimeError(
            f'Endpoint is local ({endpoint}) so only "pull" mode is supported')


def get_env(deployment: dict):
    d = datetime.datetime.now(datetime.UTC)
    env_variables = {
        'NUVLA_DEPLOYMENT_UUID': deployment['id'].split('/')[-1],
        'NUVLA_DEPLOYMENT_ID': deployment['id'],
        'NUVLA_API_KEY': deployment['api-credentials']['api-key'],
        'NUVLA_API_SECRET': deployment['api-credentials']['api-secret'],
        'NUVLA_ENDPOINT': deployment['api-endpoint'],
        'DATE_TIME': d.strftime(r'%y%m%d%H%M%S'),
        'TIMESTAMP': d.strftime(r'%s'),
    }
    deployment_group_id = deployment.get('deployment-set')
    if deployment_group_id:
        env_variables['NUVLA_DEPLOYMENT_GROUP_ID'] = deployment_group_id
        env_variables['NUVLA_DEPLOYMENT_GROUP_UUID'] = deployment_group_id.split('/')[-1]

    module_content = Deployment.module_content(deployment)

    for env_var in module_content.get('environmental-variables', []):
        env_variables[env_var['name']] = env_var.get('value')

    return env_variables


class DeploymentBase(object):

    def __init__(self, job, log=None):
        self.log = log if log else logging.getLogger(self.__class__.__name__)
        self.job = job
        self.api = job.api
        self.deployment_id = self.job['target-resource']['href']
        self.api_dpl = self.get_deployment_api(self.deployment_id)
        self.deployment: CimiResource = self.api_dpl.get(self.deployment_id)

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

    def helm_repo_cred(self, module_content: dict) -> dict:
        helm_repo_cred_id = module_content.get('helm-repo-cred')
        if not helm_repo_cred_id:
            return {}
        try:
            cred = self.job.context[helm_repo_cred_id]
        except Exception as e:
            msg = f'Failed getting {helm_repo_cred_id} from context: {e}'
            self.log.exception(msg, e)
            raise Exception(msg)
        return {k: cred.get(k) for k in ('username', 'password')}

    def helm_repo_url(self, module_content: dict) -> str:
        helm_repo_url_id = module_content.get('helm-repo-url')
        if not helm_repo_url_id:
            return ''
        try:
            infra = self.job.context[helm_repo_url_id]
        except Exception as e:
            msg = f'Failed getting {helm_repo_url_id} from context: {e}'
            self.log.exception(msg, e)
            raise Exception(msg)
        return infra.get('endpoint')

    def app_helm_release_params_set(self, release: dict):
        deployment_id = Deployment.id(self.deployment)
        deployment_owner = Deployment.owner(self.deployment)
        for k, v in release.items():
            self.create_deployment_parameter(
                deployment_id, deployment_owner,
                f'helm-{k}', v)

    def app_helm_release_params_update(self, release: dict):
        deployment_id = Deployment.id(self.deployment)
        deployment_owner = Deployment.owner(self.deployment)
        for k, v in release.items():
            self.create_update_deployment_parameter(
                deployment_id, deployment_owner,
                f'helm-{k}', v)

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

    def application_params_update(self, services: List[dict]):
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

    def _get_connector(self, deployment, connector_name) -> ConnectorCOE:
        connector_module = get_connector_module(connector_name)
        return initialize_connector(connector_module, self.job, deployment)


class DeploymentBaseStartUpdate(DeploymentBase, ABC):

    def __init__(self, action: str, job: Job, log):
        super().__init__(job, log)

        assert action in ('start_deployment',
                          'update_deployment')
        self._action = action

    @staticmethod
    def _get_action_params_base(deployment: dict, registries_auth) -> dict:
        module_content = Deployment.module_content(deployment)
        return dict(name=Deployment.uuid(deployment),
                    env=get_env(deployment),
                    files=module_content.get('files'),
                    registries_auth=registries_auth)

    @classmethod
    def _get_action_params(cls, deployment: dict, registries_auth) -> dict:
        module_content = Deployment.module_content(deployment)
        return {
            **cls._get_action_params_base(deployment, registries_auth),
            **dict(docker_compose=module_content['docker-compose'])
        }

    def _get_action_params_helm(self, deployment: dict, registries_auth) -> dict:
        module_content = Deployment.module_content(deployment)
        helm_repo_url = self.helm_repo_url(module_content)
        helm_repo_cred = self.helm_repo_cred(module_content)
        return {
            **self._get_action_params_base(deployment, registries_auth),
            **dict(deployment=deployment,
                   helm_repo_cred=helm_repo_cred,
                   helm_repo_url=helm_repo_url)
        }

    def _get_action_kwargs(self, deployment: dict) -> dict:
        # TODO: Getting action params should be based on the connector
        #  instance. By this moment we have already instantiated the
        #  connector. We should refactor this.
        registries_auth = self.private_registries_auth()
        match get_connector_name(deployment):
            case 'docker_stack' | 'docker_compose' | 'kubernetes':
                return self._get_action_params(deployment, registries_auth)
            case 'helm':
                return self._get_action_params_helm(deployment, registries_auth)
            case connector_name:
                msg = f'Unsupported connector kind: {connector_name}'
                self.log.error(msg)
                raise ValueError(msg)

    def action_on_application(self):
        deployment = self.deployment.data
        connector_name = get_connector_name(deployment)
        connector = self._get_connector(deployment, connector_name)

        kwargs = self._get_action_kwargs(deployment)
        match self._action:
            case 'start_deployment':
                result, services, extra = connector.start(**kwargs)
            case 'update_deployment':
                result, services, extra = connector.update(**kwargs)
            case _:
                msg = f'Unsupported deployment action: {self._action}'
                self.log.error(msg)
                raise ValueError(msg)
        if extra and connector_name == CONNECTOR_KIND_HELM:
            # TODO: maybe this can be done as callback to the connector action
            #  method?
            self.app_helm_release_params_update(extra)
        if result:
            self.job.set_status_message(result)

        self.application_params_update(services)

        self.job.set_progress(90)

    @override
    def handle_deployment(self):
        self.create_user_output_params()
        self.action_on_application()

    def action_on_deployment(self):
        self.log.info(
            f'{self._action} job started for {self.deployment_id}.')

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.api_dpl.set_state_started(self.deployment_id)

        return 0

    def do_work(self):
        return self.action_on_deployment()
