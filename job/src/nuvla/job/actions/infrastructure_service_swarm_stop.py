# -*- coding: utf-8 -*-

from __future__ import print_function

from ..util import create_connector_instance

from ..actions import action

import logging
from math import ceil


@action('stop_infrastructure_service_swarm')
class SwarmStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, swarm):
        swarm_service_id = swarm['id']

        credential_id = swarm['management-credential-id']

        api_credential = self.api.get(credential_id).data

        connector_instance = create_connector_instance(swarm, api_credential)

        nodes=swarm.get("nodes", [])
        stop_coe = connector_instance.stop(nodes)

        self.job.set_progress(50)

        # self.api.add("credential", new_coe["credential"])

        self.api.edit(swarm_service_id, {"state": "STOPPED"})

        self.job.set_progress(90)

        filter = 'infrastructure-services="{}"'.format(swarm_service_id)
        all_credentials = self.api.search("credential", filter=filter).resources

        for cred in all_credentials:
            if len(cred.data["infrastructure-services"]) == 1:
                self.api.delete(cred.data["id"])

        self.api.delete(swarm_service_id)

        self.job.set_progress(100)

        return 0

    def start_deployment(self):
        infra_service_id = self.job['targetResource']['href']

        swarm_data = self.api.get(infra_service_id).data

        logging.info('Starting job for new COE infrastructure service {}'.format(infra_service_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(swarm_data)
        except:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        return 10000

    def do_work(self):
        self.start_deployment()
