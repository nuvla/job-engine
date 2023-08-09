# -*- coding: utf-8 -*-
import os
import logging
import json
import re

from ..actions import action
from ...connector import nuvlabox as NB
from ...connector.kubernetes import K8sSSHKey

@action('nuvlabox_add_ssh_key', True)
class NBAddSSHKey(object):
    '''Doc string'''

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def add_ssh_key(self):
        '''Here'''
        nuvlabox_id = self.job['target-resource']['href']
        logging.debug('Adding SSH key to NuvlaBox %s', nuvlabox_id) # FIXME remove
        affected_resources = self.job['affected-resources']
        credential_id = None
        for ar in affected_resources:
            if ar.get('href', '').startswith('credential/'):
                credential_id = ar.get('href')
                break

        if credential_id:
            public_key = self.job.context[credential_id]['public-key']
            if not self._sanitize_ssh_key(public_key):
                r = "ssh public key not valid: " + public_key
                self.job.update_job(status_message=json.dumps(r))
                return 1
            self.job.set_progress(10)
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                logging.debug('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id)
                connector = K8sSSHKey(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
                connector.handle_ssh_key('add-ssh-key', public_key, credential_id, \
                    nuvlabox_id=nuvlabox_id)
            else:
                connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
                connector.connect()
                ssh_keys = connector.nuvlabox.get('ssh-keys', []) 
                if credential_id not in ssh_keys:
                    r = connector.nuvlabox_manage_ssh_key('add-ssh-key', public_key)

                    update_payload = ssh_keys + [credential_id]

                    connector.commission({"ssh-keys": update_payload})
                else:
                    r = "Requested SSH key has already been added to the \
                        NuvlaBox in the past. Nothing to do..."
                self.job.update_job(status_message=json.dumps(r))
                self.job.set_progress(100)
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        return 0

    def _sanitize_ssh_key(self, public_key):
        '''Doc string''' 
        logging.debug("Checking ssh public key %s ",public_key)
        return re.match(r'^ssh-\w+\s+\S+(\s+\S+)?$', public_key)

    def do_work(self):
        '''Doc string'''
        return self.add_ssh_key()
