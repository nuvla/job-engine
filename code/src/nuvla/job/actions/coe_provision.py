# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from nuvla.connector import connector_factory, docker_machine_connector
from nuvla.api.resources.credential import CredentialDockerSwarm, CredentialK8s
from ..actions import action

COE_TYPE_SWARM = 'swarm'
COE_TYPE_K8S = 'kubernetes'


@action('start_infrastructure_service_coe')
class COESProvisionJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, infra_service_coe):

        coe_type = infra_service_coe['subtype']
        if coe_type not in [COE_TYPE_SWARM, COE_TYPE_K8S]:
            raise Exception(f'Unknown COE type: {coe_type}')

        cloud_creds_id = infra_service_coe.get('management-credential')
        coe_custer_params = infra_service_coe.get('cluster-params', {})

        coe = connector_factory(docker_machine_connector, self.api,
                                cloud_creds_id, infra_service_coe)

        coe_certs, endpoint, coe_nodes = coe.start(coe_custer_params)
        try:
            self.job.set_progress(50)
            self._register_coe(coe_certs, coe_nodes, coe_type, endpoint,
                               infra_service_coe)
            self.job.set_progress(99)
        except Exception as ex:
            msg = f'Terminating deployed cluster. Failure in registration: {ex}'
            logging.warning(msg)
            stopped = coe.stop(nodes=coe_nodes)
            raise ex

        return 0

    def _register_coe(self, coe_certs: dict, coe_nodes: list, coe_type: str,
                      endpoint: str, infra_service_coe: dict):

        # Minimal ACL for COE credentials. Only owners can see it.
        acl = {"acl": {"owners": infra_service_coe['acl']['owners']}}
        coe_cred_data = {**coe_certs, **acl}
        infra_service_coe_id = infra_service_coe['id']
        self._set_coe_creds(coe_cred_data, coe_type,
                            infra_service_coe.get('name'),
                            infra_service_coe_id)

        self.api.edit(infra_service_coe_id,
                      {"endpoint": endpoint,
                       "state": "STARTED",
                       "nodes": coe_nodes})

    def _set_coe_creds(self, coe_cred_data, coe_type, cred_name,
                       infra_service_coe_id):
        if coe_type == COE_TYPE_SWARM:
            coe_creds = CredentialDockerSwarm \
                .build_template(coe_cred_data, infra_service_coe_id,
                                cred_name,
                                f'Credential for infrastructure service {cred_name}')
        elif coe_type == COE_TYPE_K8S:
            coe_creds = CredentialK8s \
                .build_template(coe_cred_data, infra_service_coe_id,
                                cred_name,
                                f'Credential for infrastructure service {cred_name}')
        else:
            raise Exception(f'Unknown COE type: {coe_type}')

        self.api.add("credential", coe_creds)

    def start_deployment(self):
        infra_service_coe_id = self.job['target-resource']['href']

        infra_service_coe = self.api.get(infra_service_coe_id).data

        logging.info(f'Starting job for new COE {infra_service_coe}')

        self.job.set_progress(10)

        try:
            self.handle_deployment(infra_service_coe)
        except:
            self.api.edit(infra_service_coe_id, {'state': 'ERROR'})
            raise

        return 0

    def do_work(self):
        return self.start_deployment()