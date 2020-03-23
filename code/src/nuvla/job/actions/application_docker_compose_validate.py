# -*- coding: utf-8 -*-

import logging

from nuvla.connector.docker_compose_cli_connector import DockerComposeCliConnector
from ..actions import action

action_name = 'validate-docker-compose'

log = logging.getLogger(action_name)


@action(action_name)
class ApplicationDockerComposeValidate(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            DockerComposeCliConnector.config(docker_compose=module['content']['docker-compose'])
        except Exception as ex:
            self.job.set_status_message(str(ex))
            return 1

        return 0
