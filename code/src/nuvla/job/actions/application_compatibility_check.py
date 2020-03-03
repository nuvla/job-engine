# -*- coding: utf-8 -*-

import logging

from nuvla.connector import docker_compose_cli_connector
from ..actions import action

action_name = 'application_compatibility_check'

log = logging.getLogger(action_name)


@action(action_name)
class ApplicationCompatibilityCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_config(self, module):
        connector = docker_compose_cli_connector.DockerComposeCliConnector(endpoint="unix:///var/run/docker.sock")

        last_version = self.api.get(module['versions'][-1]['href']).data

        before_last_version = self.api.get(module['versions'][-2]['href']).data if len(module['versions']) > 1 else {}

        # check if the last commit has any changes in the compose file
        # because if it doesn't, need the compatibility hasn't changed
        if last_version.get('docker-compose') != before_last_version.get('docker-compose'):
            return connector.check_app_compatibility(docker_compose=module['content']['docker-compose'])

        return None

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            module['content']['commit'] = module['content']['commit'] + " - auto compatibility check"
        except Exception as e:
            self.job.set_status_message("Cannot parse last commit from {}: {}".format(module_id, e))
            return 1

        try:
            compatibility_mode = self.check_config(module)
            log.info(compatibility_mode)
            if compatibility_mode:
                module['compatibility'] = compatibility_mode
                self.api.edit(module_id, module)
            else:
                # no need to run compatibility check cause compose file hasn't changed
                self.job.set_status_message("Nothing to do")
        except Exception as e:
            log.exception('Cannot check compatibility for %s' % module_id)
            # default to swarm compatibility
            module['compatibility'] = 'swarm'
            self.api.edit(module_id, module)
            self.job.set_status_message(e)
            return 1

        self.job.set_progress(100)

        return 0
