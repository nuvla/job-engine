# -*- coding: utf-8 -*-
import os
import logging

from ..actions import action
from ...connector import nuvlabox as NB
from ...connector.kubernetes import K8sEdgeMgmt

@action('reboot_nuvlabox', True)
class NBRebootJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def reboot(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Rebooting NuvlaBox %s', nuvlabox_id) # FIXME
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logging.debug('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id)
            self._reboot_k8s()
        else:
            connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
            r = connector.reboot()
        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION

        return 0

    def _reboot_k8s(self):
        logging.info('Now we start the connector')
        connector = K8sEdgeMgmt(self.job)
        connector.reboot()

    def do_work(self):
        return self.reboot()
    
