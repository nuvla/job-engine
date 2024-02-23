# -*- coding: utf-8 -*-

import logging
import yaml
from ...connector.docker_compose import DockerCompose
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
        aux_port_value = 1  # Some value that make docker-compose config happy, even for port number field
        aux_volume_value = '/path/{}/'

        env_variables = {'NUVLA_DEPLOYMENT_ID': str(aux_port_value),
                         'NUVLA_DEPLOYMENT_UUID': str(aux_port_value),
                         'NUVLA_DEPLOYMENT_GROUP_ID': str(aux_port_value),
                         'NUVLA_DEPLOYMENT_GROUP_UUID': str(aux_port_value),
                         'NUVLA_API_KEY': str(aux_port_value),
                         'NUVLA_API_SECRET': str(aux_port_value),
                         'NUVLA_ENDPOINT': str(aux_port_value)}

        compose_dict = yaml.safe_load(module_content['docker-compose'])

        for env_var in module_content.get('environmental-variables', []):
            for _, service in compose_dict['services'].items():
                try:
                    if 'ports' in service.keys() and any(env_var['name'] in s_port for s_port in service['ports']):
                        env_variables[env_var['name']] = str(aux_port_value)
                    else:
                        env_variables[env_var['name']] = aux_volume_value.format(aux_port_value)

                    aux_port_value += 1

                except KeyError as err:
                    log.warning("Key {} not present in compose file {}".format('ports', err))
                    continue

        return env_variables

    def do_work(self):
        module_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(module_id))

        module = self.api.get(module_id).data

        self.job.set_progress(10)

        try:
            DockerCompose.config(docker_compose=module['content']['docker-compose'],
                                 env=self.get_env_to_mute_undefined(module['content']))
            self.api.edit(module_id, {'valid': True,
                                      'validation-message': 'Docker-compose valid.'})

        except yaml.YAMLError as ymlExc:
            log.warning("Error reading .yml file. This should have already been handled by UI")
            log.exception(ymlExc)
            self.job.set_status_message(str(ymlExc))
            self.api.edit(module_id, {'valid': False,
                                      'validation-message': str(ymlExc)})

        except Exception as ex:
            self.job.set_status_message(str(ex))
            self.api.edit(module_id, {'valid': False,
                                      'validation-message': str(ex)})
            return 1

        return 0
