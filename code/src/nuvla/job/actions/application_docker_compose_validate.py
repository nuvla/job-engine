# -*- coding: utf-8 -*-
""" Nuvla Docker-compose validator module """
import logging
from typing import Dict, Any

from ..actions import action
from ...connector.docker_compose import DockerCompose, ComposeValidatorException

ACTION_NAME = 'validate-docker-compose'

log = logging.getLogger(ACTION_NAME)


@action(ACTION_NAME)
class ApplicationDockerComposeValidate:
    """
    Executes the validation of the docker-compose file for application deployment
    """
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
            except KeyError as ex:
                log.error(f"Environmental variable name not found {ex}")

        return env_variables

    def do_work(self):
        """
        Main method for validator class.

        Returns:
            0 on success, 1 otherwise

        """
        module_id = self.job['target-resource']['href']

        log.info(f'Job started for {module_id}.')

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
