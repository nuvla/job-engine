# -*- coding: utf-8 -*-

import logging

from ...connector import nuvlabox as nb
from ..actions import action
from .utils.resource_log_fetch import ResourceLogFetchJob

action_name = 'fetch_nuvlabox_log'


@action(action_name, True)
class NuvlaBoxLogFetchJob(ResourceLogFetchJob):

    def __init__(self, executor, job):
        super().__init__(executor, job)

    def all_components(self):
        return [container.name for container in self.connector.list()]

    @property
    def connector(self):
        if not self._connector:
            self._connector = \
                nb.NuvlaBox(
                    api=self.api,
                    nuvlabox_id=self.target_id,
                    job=self.job)
        return self._connector

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
