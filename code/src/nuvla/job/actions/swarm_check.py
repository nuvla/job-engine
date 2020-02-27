# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from nuvla.connector import connector_factory, docker_cli_connector
from ..actions import action

action_name = 'swarm_check'

log = logging.getLogger(action_name)


def utcnow():
    return datetime.utcnow().isoformat('T', timespec='milliseconds') + 'Z'


@action(action_name)
class CheckSwarmJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_swarm_mode(self, credential, infra):
        connector = connector_factory(docker_cli_connector, self.api,
                                      credential['id'], infra)
        info = connector.info()
        node_id = info['Swarm']['NodeID']
        managers = list(map(lambda x: x['NodeID'], info['Swarm']['RemoteManagers']))
        if node_id not in managers:
            raise AssertionError("The endpoint {} from infrastructure {} is not a manager".format(infra.get('endpoint'),
                                                                                                  infra.id))
        self.job.set_status_message(info)

    def update_infra_swarm_check(self, infrastructure_service_id, swarm_enabled=False):
        self.api.edit(infrastructure_service_id, {'swarm-enabled': swarm_enabled})

    def do_work(self):
        infra_id = self.job['target-resource']['href']

        log.info('Job {} started for {}.'.format(self.job['action'], infra_id))

        infra = self.api.get(infra_id).data

        credential = self.api.search('credential',
                                     filter='parent="{}" and subtype="swarm"'.format(infra_id)).resources[0].data

        self.job.set_progress(10)

        try:
            self.check_swarm_mode(credential, infra)
            self.update_infra_swarm_check(infra_id, swarm_enabled=True)
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], infra_id, ex))
            self.update_infra_swarm_check(infra_id)
            msg = str(ex)
            lines = msg.splitlines()
            status = lines[-1] if len(lines) > 1 else msg
            self.job.set_status_message(status)
            return 1

        return 0
