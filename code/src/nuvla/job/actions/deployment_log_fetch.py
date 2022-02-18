# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from nuvla.api.resources import Deployment
from ..actions import action
from .utils.deployment_utils import get_connector_class, get_connector_name, \
    initialize_connector, docker_stack
from .utils.resource_log_fetch import ResourceLogFetchJob

action_name = 'fetch_deployment_log'


@action(action_name, True)
class DeploymentLogFetchJob(ResourceLogFetchJob):

    def __init__(self, executor, job):
        super().__init__(executor, job)
        self.api_dpl = Deployment(self.api)
        self.deployment = self.api_dpl.get(self.resource_log_parent)
        self.connector_name = get_connector_name(self.deployment)

    @property
    def connector(self):
        if not self._connector:
            if self.connector_name == 'docker_service':
                connector_class = docker_stack
            else:
                connector_class = get_connector_class(self.connector_name)
            self._connector = initialize_connector(
                connector_class, self.job, self.deployment)
        return self._connector

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:
        if self.connector_name == 'docker_stack':
            name = f'{Deployment.uuid(self.deployment)}_{component}'
        elif self.connector_name == 'docker_service':
            name = Deployment.uuid(self.deployment)
        else:
            name = component
        return self.connector.log(name, since, lines,
                                  Deployment.uuid(self.deployment))

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
