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
            if not self._sanitize_ssh_key(pubkey):
                r = "ssh public key not valid: " + pubkey
                self.job.update_job(status_message=json.dumps(r))
                return 1
            self.job.set_progress(10)
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                logging.debug('We are using Kubernetes on nuvlabox ID : %s ',nuvlabox_id)
                result = self._add_ssh_key_k8s(pubkey, credential_id, api=self.api)
            else:
                connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
                connector.connect()
                ssh_keys = connector.nuvlabox.get('ssh-keys', [])

                if credential_id not in ssh_keys:
                    r = connector.nuvlabox_manage_ssh_key('add-ssh-key', pubkey)

                    update_payload = ssh_keys + [credential_id]

                    connector.commission({"ssh-keys": update_payload})
                    self.job.set_progress(100)
                else:
                    r = "Requested SSH key has already been added to the \
                        NuvlaBox in the past. Nothing to do..."
                self.job.update_job(status_message=json.dumps(r))
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        return 0

    def _add_ssh_key_k8s(self, pubkey, credential_id, api):
        connector = K8sSSHKey(self.job)
        nuvlabox_status = api.get("nuvlabox-status").data # FIXME
        logging.debug('The nuvlabox status from API : %s ',nuvlabox_status)
        # nuvlabox_resource = self.api.get(connector.nuvlabox_id) # FIXME
        # nuvlabox = self.nuvlabox_resource.data # FIXME
        user_home = nuvlabox_status.get('host-user-home')
        if not user_home:
            user_home = os.getenv('HOME')
            if not user_home:
                user_home = "/root" # this could be interesting point to e.g. create a user edge_login and add ssh key?
        logging.info('Attention: User home is : %s ',user_home) #FIXME
        self.job.set_progress(20)
        # ssh_keys = nuvlabox.get('ssh-keys', [])
        ssh_keys = [] # FIXME
        # logging.info("ssh keys %s", ssh_keys)
        if credential_id not in ssh_keys:
            result = connector.handleSSHKey(pubkey, user_home)
            # update_payload = ssh_keys + [update_payload] # FIXME
            # self.api.operation(nuvlabox_resource, "commission", data=update_payload) # FIXME
            self.job.set_progress(100)
        else:
            return 2
        if result.returncode == 0:
            self.job.update_job(status_message=json.dumps("SSH public key added successfully"))
            return 0
        else:
            self.job.update_job(status_message=json.dumps("SSH public adding failed."))
            return 1

    def _sanitize_ssh_key(self, pubkey):
        '''Doc string''' 
        logging.debug("Checking ssh public key %s ",pubkey)
        return re.match(r'^ssh-\w+\s+\S+(\s+\S+)?$', pubkey)

    def do_work(self):
        return self.add_ssh_key()
