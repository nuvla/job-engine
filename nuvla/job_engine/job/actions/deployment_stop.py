# -*- coding: utf-8 -*-

import logging

from nuvla.api import NuvlaError, ConnectionError
from nuvla.api.resources import Deployment, Credential
from .utils.deployment_utils import (DeploymentBase,
                                     get_connector_name,
                                     get_env)
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
        return {
            **self._get_action_params_base(deployment),
            **dict(env=env, docker_compose=docker_compose)
        }

    def _get_action_params_helm(self, deployment: dict) -> dict:
        return self._get_action_params_base(deployment)

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

        self.try_delete_deployment_credentials(self.deployment_id)

        self.api_dpl.set_state_stopped(self.deployment_id)

        return 0

    def do_work(self):
        return self.stop_deployment()
