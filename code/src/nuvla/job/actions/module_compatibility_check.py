# -*- coding: utf-8 -*-

import logging

from nuvla.connector import docker_compose_cli_connector
from ..actions import action

action_name = 'module_compatibility_check'

log = logging.getLogger(action_name)


@action(action_name)
class ModuleCompatibilityCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    @staticmethod
    def check_config(compose_file):
        connector = docker_compose_cli_connector.DockerComposeCliConnector(endpoint="unix:///var/run/docker.sock")

        return connector.check_module_compatibility(docker_compose=compose_file)

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            compose_file = module['content']['docker-compose']
            compatibility_mode = self.check_config(compose_file)
            self.api.edit(module_id, {'compatibility': compatibility_mode})
        except AssertionError as e:
            log.error('{} failed in broken {}: {}'.format(self.job['action'], module, e))
            self.job.set_status_message(e)
            return 1
        except KeyError as e:
            log.exception('Cannot check compatibility for %s' % module_id)
            # default to swarm compatibility
            self.api.edit(module_id, {'compatibility': 'swarm'})
            self.job.set_status_message(e)
            return 1

        self.job.set_progress(100)

        return 0
