# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from nuvla.connector import connector_factory, docker_cli_connector, kubernetes_cli_connector
from ..actions import action

action_name = 'credential_check'

log = logging.getLogger(action_name)


def utcnow():
    return datetime.utcnow().isoformat('T', timespec='milliseconds') + 'Z'


@action(action_name)
class CredentialCheckCOEJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_coe_swarm(self, credential):
        connector = connector_factory(docker_cli_connector, self.api,
                                      credential['id'])
        info = connector.info()
        self.job.set_status_message(info)

    def check_coe_kubernetes(self, credential):
        connector = connector_factory(kubernetes_cli_connector, self.api, credential['id'])
        version = connector.version()
        self.job.set_status_message(version)

    def update_credential_last_check(self, credential_id, status):
        self.api.edit(credential_id, {'status': status})

    def do_work(self):
        credential_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(credential_id))

        credential = self.api.get(credential_id).data

        infra_service_id = credential['parent']

        infra_service = self.api.get(infra_service_id).data

        self.job.set_progress(10)

        try:
            if infra_service['subtype'] == 'swarm':
                self.check_coe_swarm(credential)
            elif infra_service['subtype'] == 'kubernetes':
                self.check_coe_kubernetes(credential)
            self.update_credential_last_check(credential_id, 'VALID')
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], infra_service_id, ex))
            self.update_credential_last_check(credential_id, 'INVALID')
            msg = str(ex)
            lines = msg.splitlines()
            status = lines[-1] if len(lines) > 1 else msg
            self.job.set_status_message(status)
            return 1

        return 0