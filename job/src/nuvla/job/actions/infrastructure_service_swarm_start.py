# -*- coding: utf-8 -*-

from __future__ import print_function

from ..util import create_connector_instance

from ..actions import action

import logging
from math import ceil


@action('start_infrastructure_service_swarm')
class DeploymentStartJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, swarm):
        swarm_service_id = swarm['id']

        credential_id = swarm['management-credential-id']

        api_credential = self.api.get(credential_id).data

        connector_instance = create_connector_instance(swarm, api_credential)

        new_swarm_cluster = connector_instance.start()

        self.job.set_progress(50)

        service_owner = swarm['acl']['owner']['principal']

        self.api.add("credential", connector_instance.create_swarm_credential_payload(service_owner))

        endpoint = "https://{}:2376".format(connector_instance._vm_get_ip())

        self.api.edit(swarm_service_id, {"endpoint": endpoint, "state": "STARTING"})

        connector_instance.clear_connection()

        self.job.set_progress(99)
        self.api.edit(swarm_service_id, {'state': 'STARTED'})

        return 0

    def start_deployment(self):
        infra_service_id = self.job['targetResource']['href']

        swarm_data = self.api.get(infra_service_id).data

        logging.info('Starting job for new Swarm infrastructure service {}'.format(infra_service_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(swarm_data)
        except:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        return 10000

    def do_work(self):
        self.start_deployment()
        # logging.info(self.api)
