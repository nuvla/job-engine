# -*- coding: utf-8 -*-

import asyncio
import logging

from ..actions import action
from ...connector import nuvlabox_connector as NB
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


@action('nuvlabox_ssh', True)
class NBSSH(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    @staticmethod
    def generate_ssh_key() -> (str, str):
        key = rsa.generate_private_key(backend=default_backend(), public_exponent=65537, key_size=2048)
        public_key = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
        public_key = public_key.decode() + ' from nuvla'
        pem = key.private_bytes(encoding=serialization.Encoding.PEM,
                                format=serialization.PrivateFormat.TraditionalOpenSSL,
                                encryption_algorithm=serialization.NoEncryption()).decode()

        return pem, public_key

    def ssh(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Establishing SSH connection for NuvlaBox {}.'.format(nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        connector.connect()
        authn_token, user_home, ssh_user = connector.load_ssh_params()

        ssh_private, ssh_public = self.generate_ssh_key()


        try:
            asyncio.run(connector.ssh(ssh_private, ssh_public, authn_token, user_home, ssh_user))
            exit_code = 0
        except Exception as e:
            self.job.set_status_message(str(e))
            exit_code = 1
        finally:
            # need to cleanup SSH key before exiting
            remove_cmd = connector.define_ssh_mgmt_cmd('revoke-ssh-key', user_home)
            connector.docker_manage_ssh_key(remove_cmd, ssh_public, user_home)

        self.job.set_progress(100)
        return exit_code

    def do_work(self):
        return self.ssh()
