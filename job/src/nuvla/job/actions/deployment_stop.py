# -*- coding: utf-8 -*-

from __future__ import print_function

import uuid
import logging
from collections import defaultdict
from itertools import groupby

from ..util import load_module, connector_classes
from ..actions import action


def remove_prefix(prefix, input_string):
    return input_string[len(prefix):] if input_string.startswith(prefix) else input_string


def try_extract_number(input):
    val = None
    try:
        val = int(float(input))
    finally:
        return val


def kb_from_data_uuid(text):
    class NullNameSpace:
        bytes = b''

    return str(uuid.uuid3(NullNameSpace, text))


@action('stop_deployment')
class DeploymentStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.ss_api = executor.ss_api

        self._deployment = None
        self._cloud_name = None
        self._cloud_credential = None
        self._cloud_configuration = None
        self._nuvla_configuration = None
        self._user = None
        self._connector_name = None
        self._connector_instance = None

        self.handled_vms_instance_id = set([])

    def _get_deployment(self):
        return self.ss_api.cimi_get(self.job['targetResource']['href']).json

    def _get_nuvla_configuration(self):
        return self.ss_api.cimi_get('configuration/nuvla').json

    @property
    def deployment(self):
        if self._deployment is None:
            self._deployment = self._get_deployment()
        return self._deployment

    @staticmethod
    def connector_instance_userinfo(cloud_configuration, cloud_credential):
        connector_name = cloud_configuration['cloudServiceType']
        connector = load_module(connector_classes[connector_name])
        if not hasattr(connector, 'instantiate_from_cimi'):
            raise NotImplementedError('The connector "{}" is not compatible with the start_deployment job'
                                      .format(cloud_configuration['cloudServiceType']))
        return connector.instantiate_from_cimi(cloud_configuration, cloud_credential), \
               connector.get_user_info_from_cimi(cloud_configuration, cloud_credential)

    def handle_deployment(self):
        api_key = None
        try:
            api_key = self.deployment['clientAPIKey']['href']
            self.ss_api.cimi_delete(self.deployment['clientAPIKey']['href'])
        except Exception as e:
            logging.exception('Something went wrong during cleanup of api key {}: {}.'.format(api_key, e))

        filter_params = 'deployment/href="{}" and (name="instanceid" or name="credential.id")'.format(
            self.deployment['id'])
        deployment_params = self.ss_api.cimi_search('deploymentParameters', filter=filter_params,
                                                    select='nodeID,name,value').resources_list

        # Collect nodes info from params
        nodes_ids_cred_dict = defaultdict(dict)
        for dp in deployment_params:
            nodes_ids_cred_dict[dp.json['nodeID']].update({dp.json.get('name'): dp.json.get('value')})

        nodes_info = nodes_ids_cred_dict.values()
        key = lambda node_info: node_info['credential.id']
        nodes_info.sort(key=key)

        for cloud_credential_id, group_of_nodes in groupby(nodes_info, key=key):
            cloud_credential = self.ss_api.cimi_get(cloud_credential_id).json
            cloud_name = cloud_credential['connector']['href']
            cloud_configuration = self.ss_api.cimi_get(cloud_name).json
            connector_instance, user_info = \
                DeploymentStopJob.connector_instance_userinfo(cloud_configuration, cloud_credential)
            cred_instance_ids = [node['instanceid'] for node in group_of_nodes]
            logging.info('Stopping following VMs {} for {}.'.format(cred_instance_ids, cloud_credential_id))
            connector_instance.stop_vms_by_ids(cred_instance_ids)

        id_state = 'deployment-parameter/{}'.format(
            kb_from_data_uuid(':'.join([self.deployment['id'], '', 'ss:state'])))
        self.ss_api.cimi_edit(id_state, {'value': 'Done'})
        self.ss_api.cimi_edit(self.deployment['id'], {'state': 'STOPPED'})

        return 0

    def stop_deployment(self):
        logging.info('Deployment stop job started for {}.'.format(self.deployment.get('id')))

        self.job.set_progress(10)

        self.handle_deployment()

        return 10000

    def do_work(self):
        self.stop_deployment()
