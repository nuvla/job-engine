# -*- coding: utf-8 -*-

import os
import logging

from ...connector import nuvlabox as nb
from ...connector import kubernetes as k8
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
                path = '/srv/nuvlaedge/shared' # TODO parameterize this
                ca=open(f'{path}/ca.pem', encoding="utf8").read()
                key=open(f'{path}/key.pem', encoding="utf8").read()
                cert=open(f'{path}/cert.pem', encoding="utf8").read()
                kubernetes_host = os.getenv('KUBERNETES_SERVICE_HOST')
                kubernetes_port = os.getenv('KUBERNETES_SERVICE_PORT')
                if kubernetes_host and kubernetes_port:
                    endpoint=f'https://{kubernetes_host}:{kubernetes_port}'
                try:
                    self._connector = k8.Kubernetes(ca=ca,cert=cert,\
                        key=key,endpoint=endpoint,)
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
