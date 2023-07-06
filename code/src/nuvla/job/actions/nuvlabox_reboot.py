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
        reboot_cmd = "sh -c 'sleep 10 && echo b > /sysrq'" # FIX ME ... Kubernetes takes a list for manifest whereas Docker takes a string?
        # FIX ME pass the string to k8s and then convert to list? hmmm...
        logging.debug('Rebooting NuvlaBox %s', nuvlabox_id)
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logging.debug('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id)
            self._reboot_k8s(reboot_cmd)
        else:
            connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
            r = connector.reboot()
        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION

        return 0

    def _reboot_k8s(self, reboot_cmd):
        connector = K8sEdgeMgmt(self.job)
        self.job.set_progress(10)
        connector.reboot(reboot_cmd)
        self.job.set_progress(90)

    def do_work(self):
        return self.reboot()
    
