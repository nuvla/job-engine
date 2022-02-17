# -*- coding: utf-8 -*-

import copy
import logging

from ...connector import docker_machine
from nuvla.api.resources.credential import CredentialDockerSwarm, CredentialK8s
from ..actions import action

COE_TYPE_SWARM = docker_machine.COE_TYPE_SWARM
COE_TYPE_K8S = docker_machine.COE_TYPE_K8S


@action('provision_infrastructure_service_coe')
class COEProvisionJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def _provision_coe(self, infra_service_coe: dict):

        coe_type = infra_service_coe['subtype']
        if coe_type not in [COE_TYPE_SWARM, COE_TYPE_K8S]:
            raise Exception(f'Unknown COE type: {coe_type}')

        coe_custer_params = copy.deepcopy(infra_service_coe.get('cluster-params', {}))
        if 'ssh-keys' in coe_custer_params:
            # Update ssh keys as IDs by their public key values.
            ssh_pub_keys = []
            for ssh_key_id in coe_custer_params['ssh-keys']:
                # TODO: use search() to get them all at once.
                ssh_key = self.api.get(ssh_key_id).data['public-key']
                ssh_pub_keys.append(ssh_key)
            coe_custer_params['ssh-keys'] = ssh_pub_keys

        cloud_creds_id = infra_service_coe.get('management-credential')
        credential_coe = self.api.get(cloud_creds_id).data

        coe = docker_machine.instantiate_from_cimi(infra_service_coe, credential_coe)

        infra_service_id = infra_service_coe['id']
        self.api.edit(infra_service_id, {"state": "STARTING"})

        result = coe.provision(coe_custer_params)
        try:
            self.job.set_progress(90)
            self._register_coe(infra_service_coe, result)
            self.job.set_progress(100)
        except Exception as ex:
            msg = f'Terminating deployed cluster. Failure in registration: {ex}'
            logging.warning(msg)
            terminated = coe.terminate(nodes=result['nodes'])
            raise ex

        return 0

    def _register_coe(self, infra_service_coe: dict, result: dict):

        # Minimal ACL for COE credentials. Only owners can see it.
        acl = {"acl": {"owners": infra_service_coe['acl']['owners']}}

        coe_cred_data = {**result['creds'], **acl}
        infra_service_coe_id = infra_service_coe['id']
        self._set_coe_creds(coe_cred_data, infra_service_coe['subtype'],
                            infra_service_coe.get('name'),
                            infra_service_coe_id)

        cluster_params = infra_service_coe.get('cluster-params', {})
        if 'coe-manager-endpoint' in result:
            cluster_params['coe-manager-endpoint'] = result['coe-manager-endpoint']
        self.api.edit(infra_service_coe_id,
                      {'endpoint': result['endpoint'],
                       'state': 'STARTED',
                       'nodes': result['nodes'],
                       'cluster-params': cluster_params})

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

    def provision_coe(self):
        infra_service_id = self.job['target-resource']['href']

        infra_service = self.api.get(infra_service_id).data

        logging.info(f'Provision COE {infra_service_id}')

        self.job.set_progress(10)

        try:
            self._provision_coe(infra_service)
        except:
            self.api.edit(infra_service_id, {'state': 'ERROR'})
            raise

        logging.info(f'Provisioned COE {infra_service_id}')
        return 0

    def do_work(self):
        return self.provision_coe()
