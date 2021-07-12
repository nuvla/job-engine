# -*- coding: utf-8 -*-

import re
import copy
import logging
from abc import abstractmethod

from nuvla.api import Api
from ..util import override
from nuvla.api.resources import Deployment, DeploymentParameter
from nuvla.api.resources.base import ResourceNotFound
from ...connector import docker_connector, docker_cli_connector, \
    docker_compose_cli_connector, kubernetes_cli_connector
from ..actions import action

action_name = 'start_deployment'

log = logging.getLogger(action_name)


def initialize_connector(connector_class, job, deployment):
    credential_id = Deployment.credential_id(deployment)
    credential = get_from_context(job, credential_id)
    infrastructure_service = copy.deepcopy(get_from_context(job, credential['parent']))
    # if you uncomment this, the pull-mode deployment_* will only work with the NB compute-api.
    # Which means standalone ISs and k8s capable NuvlaBoxes, are not supported
    if job.is_in_pull_mode and infrastructure_service.get('subtype', '') == 'swarm':
        infrastructure_service['endpoint'] = 'https://compute-api:5000'
    return connector_class.instantiate_from_cimi(infrastructure_service, credential)


def get_from_context(job, resource_id):
    try:
        return job.context[resource_id]
    except KeyError:
        raise Exception(f'{resource_id} not found in job context')


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
                    Deployment.id(deployment), Deployment.owner(deployment),
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
        endpoint   = self.get_from_context(credential['parent'])['endpoint']
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', endpoint).group('host')

    def get_deployment_api(self, deployment_id):
        creds = Deployment._get_attr(Deployment(self.api).get(deployment_id), 'api-credentials')
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
                                 'serveraddress': infra_service['endpoint'].replace('https://', '')}
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
                                          user_id, param_name, param_value, node_id, param_description)

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

    def try_handle_raise_exception(self):
        try:
            self.handle_deployment()
        except Exception as ex:
            log.error(f"Failed to {self.job['action']} {self.deployment_id}: {ex}")
            try:
                self.job.set_status_message(repr(ex))
                if self.job.get('execution-mode', '').lower() != 'pull':
                    self.api_dpl.set_state_error(self.deployment_id)
            except Exception as ex_state:
                log.error(f'Failed to set error state for {self.deployment_id}: {ex_state}')

            raise ex


@action(action_name, True)
class DeploymentStartJob(DeploymentBase):

    def start_component(self, deployment: dict):
        connector = initialize_connector(docker_connector, self.job, deployment)

        deployment_id = Deployment.id(deployment)
        node_instance_name = Deployment.uuid(deployment)
        deployment_owner = Deployment.owner(deployment)
        module_content = Deployment.module_content(deployment)

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

        registries_auth = self.private_registries_auth(deployment)

        _, service = connector.start(
            service_name=node_instance_name,
            image=module_content['image'],
            env=get_env(deployment),
            mounts_opt=module_content.get('mounts'),
            ports_opt=module_ports,
            cpu_ratio=module_content.get('cpus'),
            memory=module_content.get('memory'),
            restart_policy_condition=restart_policy.get('condition'),
            restart_policy_delay=restart_policy.get('delay'),
            restart_policy_max_attempts=restart_policy.get('max-attempts'),
            restart_policy_window=restart_policy.get('window'),
            registry_auth=registries_auth[0] if registries_auth else None)

        # FIXME: get number of desired replicas of Replicated service from deployment. 1 for now.
        desired = 1

        deployment_parameters = (
            (DeploymentParameter.SERVICE_ID, connector.extract_vm_id(service)),
            (DeploymentParameter.HOSTNAME,   self.get_hostname()),
            (DeploymentParameter.REPLICAS_DESIRED,  str(desired)),
            (DeploymentParameter.REPLICAS_RUNNING,  '0'),
            (DeploymentParameter.CURRENT_DESIRED,   ''),
            (DeploymentParameter.CURRENT_STATE,     ''),
            (DeploymentParameter.CURRENT_ERROR,     ''),
            (DeploymentParameter.RESTART_EXIT_CODE, ''),
            (DeploymentParameter.RESTART_ERR_MSG,   ''),
            (DeploymentParameter.RESTART_TIMESTAMP, ''),
            (DeploymentParameter.RESTART_NUMBER,    ''),
            (DeploymentParameter.CHECK_TIMESTAMP,   ''),
        )

        for deployment_parameter, value in deployment_parameters:
            self.create_deployment_parameter(
                param_name=deployment_parameter['name'],
                param_value=value,
                param_description=deployment_parameter['description'],
                deployment_id=deployment_id,
                node_id=node_instance_name,
                user_id=deployment_owner)

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(service)
        self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def start_application(self, deployment: dict):
        deployment_id = Deployment.id(deployment)

        if Deployment.is_compatibility_docker_compose(deployment):
            connector = initialize_connector(docker_compose_cli_connector, self.job, deployment)
        else:
            connector = initialize_connector(docker_cli_connector, self.job, deployment)

        module_content   = Deployment.module_content(deployment)
        deployment_owner = Deployment.owner(deployment)
        docker_compose   = module_content['docker-compose']
        registries_auth  = self.private_registries_auth(deployment)

        result, services = connector.start(docker_compose=docker_compose,
                                           stack_name=Deployment.uuid(deployment),
                                           env=get_env(deployment),
                                           files=module_content.get('files'),
                                           registries_auth=registries_auth)
        self.job.set_status_message(result)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.HOSTNAME['name'],
            param_value=self.get_hostname(),
            param_description=DeploymentParameter.HOSTNAME['description'])

        application_params_update(self.api_dpl, deployment, services)

    def start_application_kubernetes(self, deployment: dict):
        deployment_id = Deployment.id(deployment)

        connector = initialize_connector(kubernetes_cli_connector, self.job, deployment)

        module_content   = Deployment.module_content(deployment)
        deployment_owner = Deployment.owner(deployment)
        docker_compose   = module_content['docker-compose']
        registries_auth  = self.private_registries_auth(deployment)

        result, services = connector.start(docker_compose=docker_compose,
                                           stack_name=Deployment.uuid(deployment),
                                           env=get_env(deployment),
                                           files=module_content.get('files'),
                                           registries_auth=registries_auth)

        self.job.set_status_message(result)

        self.create_deployment_parameter(
            deployment_id=deployment_id,
            user_id=deployment_owner,
            param_name=DeploymentParameter.HOSTNAME['name'],
            param_value=self.get_hostname(),
            param_description=DeploymentParameter.HOSTNAME['description'])

        application_params_update(self.api_dpl, deployment, services)

    @override
    def handle_deployment(self):

        if Deployment.is_component(self.deployment):
            self.start_component(self.deployment)
        elif Deployment.is_application(self.deployment):
            self.start_application(self.deployment)
        elif Deployment.is_application_kubernetes(self.deployment):
            self.start_application_kubernetes(self.deployment)

        self.create_user_output_params(self.deployment)

    def start_deployment(self):

        log.info('Job started for {}.'.format(self.deployment_id))

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.api_dpl.set_state_started(self.deployment_id)

        return 0

    def do_work(self):
        return self.start_deployment()
