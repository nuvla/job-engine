# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from ...connector import docker_machine
from nuvla.api.resources.credential import Credential
from nuvla.api import NuvlaError
from ..actions import action

COE_TYPE_SWARM = docker_machine.COE_TYPE_SWARM
COE_TYPE_K8S = docker_machine.COE_TYPE_K8S


@action('terminate_infrastructure_service_coe')
class COETerminateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def _terminate_coe(self, infra_service_coe: dict):

        coe_type = infra_service_coe['subtype']
        if coe_type not in [COE_TYPE_SWARM, COE_TYPE_K8S]:
            raise Exception(f'Unknown COE type: {coe_type}')

        cloud_creds_id = infra_service_coe.get('management-credential')
        credential_coe = self.api.get(cloud_creds_id).data

        coe = docker_machine.instantiate_from_cimi(infra_service_coe, credential_coe)

        infra_service_id = infra_service_coe['id']

        self.api.edit(infra_service_id, {"state": "TERMINATING"})

        coe.terminate(nodes=infra_service_coe.get("nodes", []))

        self.api.edit(infra_service_id, {"state": "TERMINATED"})

        self.job.set_progress(90)

        self._delete_coe_creds(infra_service_id)

        self.api.delete(infra_service_id)

        # Attempt deleting IS group we were in if empty.
        isg_id = infra_service_coe.get('parent', None)
        if isg_id:
            isg = self.api.get(isg_id).data
            if not isg.get('infrastructure-services', []):
                self.api.delete(isg_id)

        self.job.set_progress(100)

    def _delete_coe_creds(self, infra_service_id):
        cred_api = Credential(self.api, subtype='dummy')
        credentials = cred_api.find_parent(infra_service_id)
        for credential in credentials:
            cred_id = Credential.id(credential)
            try:
                cred_api.delete(cred_id)
            except (NuvlaError, ConnectionError):
                logging.error(f'Failed to delete {cred_id}')

    def terminate_coe(self):
        infra_service_id = self.job['target-resource']['href']

        infra_service = self.api.get(infra_service_id).data

        logging.info(f'Terminate COE {infra_service_id}')

        self.job.set_progress(10)

        try:
            self._terminate_coe(infra_service)
        except Exception:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        logging.info(f'Deleted COE {infra_service_id}')
        return 0

    def do_work(self):
        return self.terminate_coe()
