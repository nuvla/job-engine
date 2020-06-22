# -*- coding: utf-8 -*-

import logging

from ..actions import action
from nuvla.connector import nuvlabox_connector as NB


@action('nuvlabox_add_ssh_key')
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
            pubkey = self.api.get(credential_id).data['public-key']
            connector.connect()
            ssh_keys = connector.nuvlabox.get('ssh-keys', [])

            if credential_id not in ssh_keys:
                r = connector.start(api_action_name="add-ssh-key", method='post',
                                    payload=pubkey, headers={"Content-Type": "text/plain"})

                logging.info(r)

                update_payload = ssh_keys.append(credential_id)
                logging.info(update_payload)

                connector.update(update_payload)
        else:
            raise Exception('Cannot find any reference to an existing credential ID')

        return 0

    def do_work(self):
        return self.add_ssh_key()
