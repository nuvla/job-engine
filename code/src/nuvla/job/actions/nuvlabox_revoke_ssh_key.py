# -*- coding: utf-8 -*-

import logging
import json

from ..actions import action
from nuvla.connector import nuvlabox_connector as NB


@action('nuvlabox_revoke_ssh_key')
class NBRevokeSSHKey(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def revoke_ssh_key(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Removing SSH key from NuvlaBox {}.'.format(nuvlabox_id))
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
            pubkey = self.job.context[credential_id]['public-key']
            r = connector.start(api_action_name="revoke-ssh-key", method='post',
                                payload=pubkey, headers={"Content-Type": "text/plain"})

            ssh_keys = connector.nuvlabox.get('ssh-keys', [])
            try:
                ssh_keys.remove(credential_id)
                update_payload = {"ssh-keys": ssh_keys}
            except ValueError:
                # for some reason the key is not in this list...continue anyway, but no need to edit the NB resource
                update_payload = {}

            connector.update(update_payload)
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        self.job.update_job(status_message=json.dumps(r))

        return 0

    def do_work(self):
        return self.revoke_ssh_key()
