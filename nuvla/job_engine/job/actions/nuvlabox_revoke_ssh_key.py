# -*- coding: utf-8 -*-

import os
import logging
import json

from ..actions import action
from ...connector import nuvlabox as NB
from ...connector.kubernetes import K8sSSHKey

@action('nuvlabox_revoke_ssh_key', True)
class NBRevokeSSHKey(object):
    """
    Function to handle the revoking an ssh key from a  nuvlabox
        
    Used for kubernetes or docker
    """

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def revoke_ssh_key(self):
        '''Here'''
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Removing SSH key from NuvlaBox %s', nuvlabox_id)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        # for this, we need to get the respective SSH public key
        affected_resources = self.job['affected-resources']
        credential_id = None
        for ar in affected_resources:
            if ar.get('href', '').startswith('credential/'):
                credential_id = ar.get('href')
                break

        if credential_id:
            public_key = self.job.context[credential_id]['public-key']
            self.job.set_progress(10)
            if os.getenv('KUBERNETES_SERVICE_HOST'):
                logging.debug('Using Kubernetes on NuvlaEdge: %s', nuvlabox_id)
                connector = K8sSSHKey(job=self.job, nuvlabox_id=nuvlabox_id)
                connector.manage_ssh_key(K8sSSHKey.ACTION_REVOKE, public_key,
                                         credential_id, nuvlabox_id=nuvlabox_id)
            else:
                connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
                r = connector.nuvlabox_manage_ssh_key('revoke-ssh-key', public_key)
                ssh_keys = connector.nuvlabox.get('ssh-keys', [])
                try:
                    ssh_keys.remove(credential_id)
                    update_payload = {"ssh-keys": ssh_keys}
                except ValueError:
                # for some reason the key is not in this list...continue anyway, but no need to edit the NB resource
                    update_payload = None

                if update_payload is not None:
                    connector.commission(update_payload)
                self.job.update_job(status_message=json.dumps(r))
                self.job.set_progress(100)
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        return 0

    def do_work(self):
        return self.revoke_ssh_key()
