# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from nuvla.api.resources import Deployment
from ..actions import action
from .utils.deployment_utils import get_connector_class, get_connector_name, \
    initialize_connector, docker_compose
from .utils.resource_log_fetch import ResourceLogFetchJob

action_name = 'fetch_deployment_log'


@action(action_name, True)
class DeploymentLogFetchJob(ResourceLogFetchJob):

    def __init__(self, *args, **kwargs):
        super(ResourceLogFetchJob, self).__init__(*args, **kwargs)
        self.deployment = self.api_dpl.get(self.target_id)

    @property
    def connector(self):
        if not self._connector:
            connector_name = get_connector_name(self.deployment)
            if connector_name == 'docker_service':
                connector_class = docker_compose
            else:
                connector_class = get_connector_class(connector_name)
            self._connector = initialize_connector(
                connector_class, self.job, self.deployment)
        return self._connector

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:
        return self.connector.log(component, since, lines,
                                  Deployment.uuid(self.deployment))

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
