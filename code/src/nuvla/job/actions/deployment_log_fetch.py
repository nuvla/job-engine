# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector, docker_cli_connector
from nuvla.api import NuvlaError, ConnectionError
from .deployment import Deployment
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

        existing_log = deployment_log.get('log', [])

        since = deployment_log.get('since')

        head_or_tail = deployment_log.get('head-or-tail', 'all')

        lines = deployment_log.get('lines', 200)

        deployment_id = deployment_log['parent']

        deployment = self.api_dpl.get(deployment_id)

        deployment_uuid = Deployment.uuid(deployment)

        connector = connector_factory(docker_cli_connector, self.api, deployment.get('parent'))

        if Deployment.is_application(deployment):
            docker_service_name = deployment_uuid + '_' + service_name
        else:
            docker_service_name = deployment_uuid

        tmp_since = last_timestamp or since
        since_opt = ['--since', tmp_since] if tmp_since else []

        list_opts = ['-t', '--no-trunc'] + since_opt + [docker_service_name]

        result = connector.log(list_opts) \
            .stdout.decode('UTF-8').strip().split('\n')

        new_last_timestamp = DeploymentLogFetchJob.extract_last_timestamp(result)

        update_deployment_log = {'log': existing_log + result}

        if new_last_timestamp:
            update_deployment_log['last-timestamp'] = new_last_timestamp

        self.api.edit(deployment_log['id'], update_deployment_log)

    def fetch_deployment_log(self):
        deployment_log_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_log_id))

        deployment_log = self.api.get(deployment_log_id).data

        self.job.set_progress(10)

        try:
            self.fetch_log(deployment_log)
        except Exception as ex:
            log.error('Failed to fetch {0}: {1}'.format(deployment_log_id, ex))
            try:
                self.job.set_status_message(repr(ex))
            except Exception as ex_state:
                log.error('Failed to set error state for {0}: {1}'
                          .format(deployment_log_id, ex_state))

            raise ex

        return 0

    def do_work(self):
        return self.fetch_deployment_log()
