# -*- coding: utf-8 -*-

import logging

from ...connector import nuvlabox_connector as nb
from ..actions import action
from .resource_log_fetch import ResourceLogFetchJob
from datetime import datetime

action_name = 'fetch_nuvlabox_log'

log = logging.getLogger(action_name)


@action(action_name, True)
class NuvlaBoxLogFetchJob(ResourceLogFetchJob):

    def __init__(self, *args, **kwargs):
        super(ResourceLogFetchJob, self).__init__(*args, **kwargs)
        self.connector = nb.NuvlaBoxConnector(
            api=self.api,
            nuvlabox_id=self.resource_log['parent'], job=self.job)

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:
        return self.connector.log(component, since, lines)

    def all_components(self):
        return [container.name for container in self.connector.list()]

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
