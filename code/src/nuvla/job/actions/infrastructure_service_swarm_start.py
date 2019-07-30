# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from nuvla.connector import connector_factory, docker_machine_connector
from ..actions import action


@action('start_infrastructure_service_swarm')
class SwarmStartJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, swarm):
        connector_instance = connector_factory(docker_machine_connector, self.api,
                                               swarm.get('management-credential-id'))

        new_coe = connector_instance.start()

        self.job.set_progress(50)

        self.api.add("credential", new_coe["credential"])

        endpoint = "https://{}:2376".format(new_coe["ip"])

        swarm_service_id = swarm['id']

        self.api.edit(swarm_service_id, {"endpoint": endpoint, "state": "STARTING", "nodes": [new_coe["node"]]})

        self.job.set_progress(99)
        self.api.edit(swarm_service_id, {'state': 'STARTED'})

        return 0

    def start_deployment(self):
        infra_service_id = self.job['target-resource']['href']

        swarm_data = self.api.get(infra_service_id).data

        logging.info('Starting job for new COE infrastructure service {}'.format(infra_service_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(swarm_data)
        except:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        return 0

    def do_work(self):
        self.start_deployment()
