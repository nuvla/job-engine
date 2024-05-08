# -*- coding: utf-8 -*-

import os
import logging

from ...connector import nuvlabox as nb
from ...connector import kubernetes as k8s
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
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                logging.debug("Kubernetes connector used.")
                try:
                    self._connector = k8s.K8sLogging(self.job)
                except Exception as e:
                    logging.error(f'Kubernetes error:\n{str(e)}')
            else:
                self._connector = \
                    nb.NuvlaBox(
                        api=self.api,
                        nuvlabox_id=self.resource_log_parent,
                        job=self.job)

        return self._connector

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(action_name)
        return self._log
