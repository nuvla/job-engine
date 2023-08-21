# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from nuvla.api.resources import Deployment
from ..actions import action
from .utils.deployment_utils import (get_connector_class,
                                     get_connector_name,
                                     initialize_connector,
                                     docker_stack,
                                     get_env)
from .utils.resource_log_fetch import ResourceLogFetchJob

action_name = 'fetch_deployment_log'


@action(action_name, True)
class DeploymentLogFetchJob(ResourceLogFetchJob):

    def __init__(self, executor, job):
        super().__init__(executor, job)
        self.api_dpl = Deployment(self.api)
        self.deployment = self.api_dpl.get(self.resource_log_parent)
        self._connector_name = None

    @property
    def connector(self):
        if not self._connector:
            if self.connector_name == 'docker_service':
                connector_class = docker_stack
            else:
                connector_class = get_connector_class(self.connector_name)
            self._connector = initialize_connector(connector_class, self.job, self.deployment)
        return self._connector

    @property
    def connector_name(self):
        if not self._connector_name:
            self._connector_name = get_connector_name(self.deployment)
        return self._connector_name

    def get_kubernetes_log(self, component, since, lines):
        return self.connector.log(component, since, lines,
                                  namespace=Deployment.uuid(self.deployment))

    def get_docker_compose_log(self, component, since, lines):
        module_content = Deployment.module_content(self.deployment)
        return self.connector.log(
            component, since, lines,
            deployment_uuid=Deployment.uuid(self.deployment),
            docker_compose=module_content['docker-compose'],
            env=get_env(self.deployment.data)
        )

    def get_docker_stack_log(self, component, since, lines):
        if self.connector_name == 'docker_service':
            name = Deployment.uuid(self.deployment)
        else:
            name = f'{Deployment.uuid(self.deployment)}_{component}'
        return self.connector.log(name, since, lines)

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:
        return {
            'docker_service': self.get_docker_stack_log,
            'docker_stack': self.get_docker_stack_log,
            'docker_compose': self.get_docker_compose_log,
            'kubernetes': self.get_kubernetes_log
        }[self.connector_name](component, since, lines)

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
