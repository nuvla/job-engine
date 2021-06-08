# -*- coding: utf-8 -*-

import logging
import json

from ..actions import action
from ...connector import nuvlabox_connector as NB


@action('nuvlabox_add_ssh_key', True)
class NBAddSSHKey(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def add_ssh_key(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Adding SSH key to NuvlaBox {}.'.format(nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        # for this, we need to get the respective SSH public key
        affected_resources = self.job['affected-resources']
        credential_id = None
        for ar in affected_resources:
            if ar.get('href', '').startswith('credential/'):
                credential_id = ar.get('href')
                break

        if credential_id:
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

    def do_work(self):
        return self.add_ssh_key()
