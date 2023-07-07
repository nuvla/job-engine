# -*- coding: utf-8 -*-
import os
import logging
import json

from ..actions import action
from ...connector import nuvlabox as NB
from ...connector.kubernetes import K8sSSHKey

@action('nuvlabox_add_ssh_key', True)
class NBAddSSHKey(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def add_ssh_key(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Adding SSH key to NuvlaBox %s', nuvlabox_id)
        # FIXME need to determine our driver here.
        # if os.getenv('KUBERNETES_SERVICE_HOST'):
          #   logging.info('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id) # FIXME remove
            # self._add_ssh_key_k8s()
        # else:
        connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        # for this, we need to get the respective SSH public key
        affected_resources = self.job['affected-resources']
        credential_id = None
        for ar in affected_resources:
            if ar.get('href', '').startswith('credential/'):
                credential_id = ar.get('href')
                break

        if credential_id:
            logging.info("Connecting to %s : ", nuvlabox_id)
            connector.connect()
            pubkey = self.job.context[credential_id]['public-key']
            ssh_keys = connector.nuvlabox.get('ssh-keys', [])

            if credential_id not in ssh_keys:
                r = connector.nuvlabox_manage_ssh_key('add-ssh-key', pubkey)

                update_payload = ssh_keys + [credential_id]

                connector.commission({"ssh-keys": update_payload})
                self.job.set_progress(100)
            else:
                r = "Requested SSH key has already been added to the NuvlaBox in the past. Nothing to do..."
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        self.job.update_job(status_message=json.dumps(r))

        return 0

    def _add_ssh_key_k8s(self):
        logging.info('We must wait for the other pull request to be merged.') # FIXME
        connector = K8sSSHKey(self.job)
        self.job.set_progress(10)
        # connector.reboot(reboot_cmd)
        self.job.set_progress(90)

    def do_work(self):
        return self.add_ssh_key()
