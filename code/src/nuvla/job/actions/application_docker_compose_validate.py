# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

from ..actions import action
from ...connector.docker_compose import DockerCompose, ComposeValidatorException

action_name = 'validate-docker-compose'

log = logging.getLogger(action_name)


@action(action_name)
class ApplicationDockerComposeValidate(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    @staticmethod
    def get_env_to_mute_undefined(module_content: Dict[str, Any]) -> Dict[str, str]:
        """
        Initializes a dictionary with an entry for every environmental variable parsed.
        In sort, this is a variable parser.

        Args:
            module_content: Dictionary where the env variables are parsed

        Returns:
            a dictionary with an entry for every environmental variable parsed.
        """
        env_variables: Dict[str, str] = {}
        it_env: Dict[str, Any]
        for it_env in module_content.get('environmental-variables', []):
            try:
                env_variables[it_env['name']] = it_env.get('value', '')
            except KeyError as keyErr:
                log.error("Environmental variable name not found {}".format(keyErr))

        return env_variables

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            DockerCompose.config(docker_compose=module['content']['docker-compose'],
                                 env=self.get_env_to_mute_undefined(module['content']),
                                 )
            self.api.edit(module_id, {'valid': True,
                                      'validation-message': 'Docker-compose valid.'})

        except ComposeValidatorException as ex:
            self.job.set_status_message(str(ex))
            self.api.edit(module_id, {'valid': False,
                                      'validation-message': str(ex)})
            return 1

        return 0
