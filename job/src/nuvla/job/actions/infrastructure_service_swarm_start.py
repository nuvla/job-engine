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

    def create_deployment_parameter(self, deployment_id, user, param_name, param_value=None, node_id=None,
                                    param_description=None):
        parameter = {'name': param_name,
                     'deployment': {'href': deployment_id},
                     'acl': {'owner': {'principal': 'ADMIN',
                                       'type': 'ROLE'},
                             'rules': [{'principal': user,
                                        'type': 'USER',
                                        'right': 'MODIFY'}]}}
        if node_id:
            parameter['node-id'] = node_id
        if param_description:
            parameter['description'] = param_description
        if param_value:
            parameter['value'] = param_value
        return self.api.add('deployment-parameter', parameter)

    @staticmethod
    def get_port_name_value(port_mapping):
        port_details = port_mapping.split(':')
        return '.'.join([port_details[0], port_details[2]]), port_details[1]

    def get_mounts_from_data_records(self, data_records):
        mounts_opt = set([])

        count_limit = 10000
        for i in range(int(ceil(len(data_records) / count_limit))):
            ids = data_records[i * count_limit:(i + 1) * count_limit]
            ids = map(lambda x: 'id={}'.format(x), ids)
            result = self.api.search('data-record', filter=' or '.join(ids))
            for data_record in result.resources:  # FIXME Hardcoded nfs and mount path
                mount_str = 'type=volume,volume-opt=o=addr={},'.format(data_record.data['data:nfsIP']) + \
                            'volume-opt=device=:{},'.format(data_record.data['data:nfsDevice']) + \
                            'volume-opt=type=nfs,dst={}'.format('/gssc/data/nuvla' + data_record.data['data:nfsDevice'])
                mounts_opt.add(mount_str)
        return mounts_opt

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


        # self.create_deployment_parameter(
        #     deployment_id=deployment_id,
        #     user=deployment_owner,
        #     param_name='instance-id',
        #     param_value=connector_instance.extract_vm_id(container),
        #     param_description='Instance ID',
        #     node_id=node_instance_name)
        #
        # self.create_deployment_parameter(
        #     deployment_id=deployment_id,
        #     user=deployment_owner,
        #     param_name='hostname',
        #     param_value=connector_instance.extract_vm_ip(container),
        #     param_description='Hostname',
        #     node_id=node_instance_name)

        # ports_mapping = connector_instance.extract_vm_ports_mapping(container)
        # if ports_mapping:
        #     for port_mapping in ports_mapping.split():
        #         port_param_name, port_param_value = self.get_port_name_value(port_mapping)
        #         self.create_deployment_parameter(
        #             deployment_id=deployment_id,
        #             user=deployment_owner,
        #             param_name=port_param_name,
        #             param_value=port_param_value,
        #             node_id=node_instance_name)
        #
        # for output_param in api_deployment['module']['content'].get('output-parameters', []):
        #     self.create_deployment_parameter(deployment_id=deployment_id,
        #                                      user=deployment_owner,
        #                                      param_name=output_param['name'],
        #                                      param_description=output_param.get('description'),
        #                                      node_id=node_instance_name)
        #
        # self.api.edit(api_deployment['id'], {'state': 'STARTED'})

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
