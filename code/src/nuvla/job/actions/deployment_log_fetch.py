# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_cli_connector, \
    docker_compose_cli_connector, kubernetes_cli_connector
from .nuvla import Deployment
from ..actions import action

action_name = 'fetch_deployment_log'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentLogFetchJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    @staticmethod
    def extract_last_timestamp(result):
        timestamp = result[-1].strip().split(' ')[0]
        # timestamp limit precision to be compatible with server to pico
        return timestamp[:23] + 'Z' if timestamp else None

    def fetch_log(self, deployment_log):

        service_name = deployment_log['service']

        last_timestamp = deployment_log.get('last-timestamp')

        since = deployment_log.get('since')

        lines = deployment_log.get('lines', 200)

        deployment_id = deployment_log['parent']

        deployment = self.api_dpl.get(deployment_id)

        deployment_uuid = Deployment.uuid(deployment)

        tmp_since = last_timestamp or since

        if Deployment.is_application_kubernetes(deployment):
            connector = connector_factory(kubernetes_cli_connector,
                                          self.api, deployment.get('parent'))
            since_opt = ['--since-time', tmp_since] if tmp_since else []
            list_opts = [service_name, '--timestamps=true', '--tail', str(lines),
                         '--namespace', deployment_uuid] + since_opt
        else:
            is_docker_compose = (Deployment.module(deployment).get('compatibility') == "docker-compose")
            if is_docker_compose:
                connector = connector_factory(docker_compose_cli_connector, self.api, deployment.get('parent'))
                no_trunc = []
            else:
                connector = connector_factory(docker_cli_connector, self.api, deployment.get('parent'))
                no_trunc = ['--no-trunc']

            if Deployment.is_application(deployment):
                if is_docker_compose:
                    docker_service_name = self.api_dpl.get_parameter(deployment_uuid, service_name, 'service-id')
                else:
                    docker_service_name = deployment_uuid + '_' + service_name
            else:
                docker_service_name = deployment_uuid

            since_opt = ['--since', tmp_since] if tmp_since else []

            list_opts = ['-t'] + no_trunc + since_opt + [docker_service_name]

        result = connector.log(list_opts).strip().split('\n')[:lines]

        new_last_timestamp = DeploymentLogFetchJob.extract_last_timestamp(result)

        update_deployment_log = {'log': result}

        if new_last_timestamp:
            update_deployment_log['last-timestamp'] = new_last_timestamp

        self.api.edit(deployment_log['id'], update_deployment_log)

    def fetch_deployment_log(self):
        deployment_log_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_log_id))

        deployment_log = self.api.get(
            deployment_log_id, select='id, parent, service, since, lines, last-timestamp').data

        self.job.set_progress(10)

        try:
            self.fetch_log(deployment_log)
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], deployment_log_id, ex))
            try:
                self.job.set_status_message(repr(ex))
            except Exception as ex_state:
                log.error('Failed to set error state for {0}: {1}'
                          .format(deployment_log_id, ex_state))

            raise ex

        return 0

    def do_work(self):
        return self.fetch_deployment_log()
