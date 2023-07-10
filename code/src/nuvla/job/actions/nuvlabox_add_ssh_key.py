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

        logging.info('Adding SSH key to NuvlaBox %s', nuvlabox_id) # FIXME remove
        # FIXME need to determine our driver here.
        # if os.getenv('KUBERNETES_SERVICE_HOST'):
          #   logging.info('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id) # FIXME remove
          #   self._add_ssh_key_k8s()
        # else:
          #   connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        # for this, we need to get the respective SSH public key
        affected_resources = self.job['affected-resources']
        credential_id = None
        for ar in affected_resources:
            if ar.get('href', '').startswith('credential/'):
                credential_id = ar.get('href')
                break

        if credential_id:
            pubkey = self.job.context[credential_id]['public-key']
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                logging.info('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id) # FIXME remove
                self._add_ssh_key_k8s(pubkey) # FIXME we do also need to know the expected home directory on the host system.
            else:
                connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

            connector.connect()
            ssh_keys = connector.nuvlabox.get('ssh-keys', [])

            if credential_id not in ssh_keys:
                # FIXME actually maybe here we can test for Kubernetes?
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

    def _add_ssh_key_k8s(self, pubkey):
        logging.info('We must wait for the other pull request to be merged.') # FIXME
        connector = K8sSSHKey(self.job)
        # FIXME ... get the home directory here?
        nuvlabox_status = self.api.get("nuvlabox-status").data
        user_home = nuvlabox_status.get('host-user-home')
        logging.info('Extracted a user home value of : %s ',user_home)
        self.job.set_progress(10)
        connector.handleSSHKey()
        self.job.set_progress(90)

    def do_work(self):
        return self.add_ssh_key()
