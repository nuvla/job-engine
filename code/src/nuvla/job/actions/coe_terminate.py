# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from nuvla.connector import connector_factory, docker_machine_connector
from ..actions import action


@action('stop_infrastructure_service_coe')
class SwarmStopJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, swarm):
        connector_instance = connector_factory(docker_machine_connector, self.api,
                                               swarm.get('management-credential-id'))

        nodes = swarm.get("nodes", [])
        connector_instance.stop(nodes=nodes)

        self.job.set_progress(50)

        swarm_service_id = swarm['id']

        self.api.edit(swarm_service_id, {"state": "STOPPED"})

        self.job.set_progress(90)

        filter_services = 'infrastructure-services="{}"'.format(swarm_service_id)
        all_credentials = self.api.search("credential", filter=filter_services).resources

        for cred in all_credentials:
            if len(cred.data["infrastructure-services"]) == 1:
                self.api.delete(cred.data["id"])

        self.api.delete(swarm_service_id)

        self.job.set_progress(100)

    def start_deployment(self):
        infra_service_id = self.job['target-resource']['href']

        swarm_data = self.api.get(infra_service_id).data

        logging.info('Starting job for new COE infrastructure service {}'.format(infra_service_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(swarm_data)
        except Exception:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        return 0

    def do_work(self):
        return self.start_deployment()