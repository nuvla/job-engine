# -*- coding: utf-8 -*-

import logging

from nuvla.api import NuvlaError, ConnectionError
from nuvla.api.resources import Deployment, Credential
from .utils.deployment_utils import (DeploymentBase,
                                     get_connector_name,
                                     get_env)
from .utils.mm3_client import Mm3ClientError
from ..util import override
from ..actions import action

action_name = 'stop_deployment'


@action(action_name, True)
class DeploymentStopJob(DeploymentBase):

    def __init__(self, job):
        super().__init__(job, logging.getLogger(action_name))

    def try_delete_deployment_credentials(self, deployment_id):
        cred_api = Credential(self.api, subtype='dummy')
        credentials = cred_api.find_parent(deployment_id)
        for credential in credentials:
            try:
                cred_api.delete(Credential.id(credential))
            except (NuvlaError, ConnectionError):
                pass

    @staticmethod
    def _get_action_params_base(deployment: dict) -> dict:
        return dict(name=Deployment.uuid(deployment))

    def _get_action_params(self, deployment: dict) -> dict:
        env = get_env(deployment)
        docker_compose = Deployment.module_content(deployment)['docker-compose']

        args = {
            **self._get_action_params_base(deployment),
            **dict(env=env, docker_compose=docker_compose)
        }

        # Payload could be empty or NoneType
        if self.job.payload:
            args.update(self.job.payload)
        return args

    def _get_action_params_helm(self, deployment: dict) -> dict:
        return {
            **self._get_action_params_base(deployment),
            **dict(module_content=Deployment.module_content(deployment))
        }

    def _get_action_kwargs(self, deployment: dict) -> dict:
        # TODO: Getting action params should be based on the connector
        #  instance. By this moment we have already instantiated the
        #  connector. We should refactor this.
        match get_connector_name(deployment):
            case 'docker_stack' | 'docker_compose' | 'kubernetes':
                return self._get_action_params(deployment)
            case 'helm':
                return self._get_action_params_helm(deployment)
            case connector_name:
                msg = f'Unsupported connector kind: {connector_name}'
                self.log.error(msg)
                raise ValueError(msg)

    def stop_application(self):
        if self.is_mec_job():
            match self.mec_operation_type():
                case 'TERMINATE':
                    southbound_app_instance_id = self.get_mec_app_instance_id()
                    if not southbound_app_instance_id:
                        raise Mm3ClientError(f'MEC app instance id not found for {self.deployment_id}')
                    response = self.mm3_client().delete_app_instance(southbound_app_instance_id)
                    self.persist_mec_operation_id(self.extract_mec_operation_id(response))
                    self.job.set_status_message(f'Mm3 terminate succeeded via {self.mepm_endpoint()}')
                    return
                case 'OPERATE':
                    southbound_app_instance_id = self.get_mec_app_instance_id()
                    if not southbound_app_instance_id:
                        raise Mm3ClientError(f'MEC app instance id not found for {self.deployment_id}')
                    target_state = self.get_mec_change_state_to()
                    if target_state not in ('STARTED', 'STOPPED'):
                        raise Mm3ClientError(f'Unsupported MEC operate target state: {target_state}')
                    response = self.mm3_client().operate_app_instance(southbound_app_instance_id, target_state)
                    self.persist_mec_operation_id(self.extract_mec_operation_id(response))
                    self.job.set_status_message(f'Mm3 operate {target_state} succeeded via {self.mepm_endpoint()}')
                    return

        deployment = self.deployment.data
        connector = self._get_connector(deployment,
                                        get_connector_name(deployment))

        kwargs = self._get_action_kwargs(deployment)
        result = connector.stop(**kwargs)

        self.job.set_status_message(result)

    @override
    def handle_deployment(self):
        self.stop_application()

    def stop_deployment(self):
        self.log.info(f'{action_name} job started for {self.deployment_id}.')

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        # MEC lifecycle jobs can chain STOPPED -> TERMINATE or STOPPED -> STARTED.
        # Keep deployment API credentials so subsequent MEC jobs can still
        # authenticate against Nuvla using the deployment's api-credentials.
        if not self.is_mec_job():
            self.try_delete_deployment_credentials(self.deployment_id)

        if self.is_mec_job():
            # The Mm3 callback reconciles the final state for MEC-facing
            # deployments once the southbound operation really converges.
            return 0

        self.api_dpl.set_state_stopped(self.deployment_id)

        return 0

    def do_work(self):
        return self.stop_deployment()
