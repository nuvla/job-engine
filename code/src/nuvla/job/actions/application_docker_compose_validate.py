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

    @staticmethod
    def get_env_to_mute_undefined(module_content):
        value = "some-value"
        env_variables = {'NUVLA_DEPLOYMENT_ID': value,
                         'NUVLA_DEPLOYMENT_UUID': value,
                         'NUVLA_API_KEY': value,
                         'NUVLA_API_SECRET': value,
                         'NUVLA_ENDPOINT': value}

        for env_var in module_content.get('environmental-variables', []):
            env_variables[env_var['name']] = value

        return env_variables

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            DockerComposeCliConnector.config(docker_compose=module['content']['docker-compose'],
                                             env=self.get_env_to_mute_undefined(module['content']))
            self.api.edit(module_id, {'valid': True,
                                      'validation-message': 'Docker-compose valid.'})
        except Exception as ex:
            self.job.set_status_message(str(ex))
            self.api.edit(module_id, {'valid': False,
                                      'validation-message': str(ex)})
            return 1

        return 0
