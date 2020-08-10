# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from nuvla.connector import connector_factory, docker_machine_connector
from nuvla.api.resources.credential import Credential
from nuvla.api import NuvlaError
from ..actions import action

COE_TYPE_SWARM = docker_machine_connector.COE_TYPE_SWARM
COE_TYPE_K8S = docker_machine_connector.COE_TYPE_K8S


@action('start_infrastructure_service_coe')
class COEStartJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def _start_coe(self, infra_service_coe: dict):

        coe_type = infra_service_coe['subtype']
        if coe_type not in [COE_TYPE_SWARM, COE_TYPE_K8S]:
            raise Exception(f'Unknown COE type: {coe_type}')

        cloud_creds_id = infra_service_coe.get('management-credential')
        coe = connector_factory(docker_machine_connector, self.api,
                                cloud_creds_id, infra_service_coe)

        infra_service_id = infra_service_coe['id']

        self.api.edit(infra_service_id, {"state": "STARTING"})

        # TODO: pass self.job.set_progress as callback to set progress.
        coe.start(nodes=infra_service_coe.get("nodes", []))

        self.api.edit(infra_service_id, {"state": "STARTED"})

        self.job.set_progress(100)

    def start_coe(self):
        infra_service_id = self.job['target-resource']['href']

        infra_service = self.api.get(infra_service_id).data

        logging.info(f'Start COE {infra_service_id}')

        self.job.set_progress(10)

        try:
            self._start_coe(infra_service)
        except Exception:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        logging.info(f'Started COE {infra_service_id}')
        return 0

    def do_work(self):
        return self.start_coe()
