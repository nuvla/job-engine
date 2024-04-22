# -*- coding: utf-8 -*-
import os
import logging

from ..actions import action
from ...connector.nuvlabox import NuvlaBox
from ...connector.kubernetes import K8sEdgeMgmt
from ...job.job import Job


@action('reboot_nuvlabox', True)
class NBRebootJob(object):

    def __init__(self, _, job: Job):
        self.job = job
        self.api = job.api

    def reboot(self):

        logging.info('Rebooting NuvlaEdge %s', self.job['target-resource']['href'])

        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logging.info('Found kubernetes installation.')
            ret = self._reboot_k8s()
        else:
            logging.info('Found docker installation.')
            ret = self._reboot_docker()

        logging.info(f'Reboot action called. Output: {ret}')

        return 0

    def _reboot_docker(self) -> str:
        connector = NuvlaBox(api=self.api, job=self.job,
                             nuvlabox_id=self.job['target-resource']['href'])
        return connector.reboot()

    def _reboot_k8s(self) -> str:
        connector = K8sEdgeMgmt(self.job)
        self.job.set_progress(10)
        ret = connector.reboot()
        self.job.set_progress(90)
        return ret

    def do_work(self):
        return self.reboot()
