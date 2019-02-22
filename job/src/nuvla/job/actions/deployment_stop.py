# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
from collections import defaultdict
from itertools import groupby

from ..util import create_connector_instance, from_data_uuid
from ..actions import action


@action('stop_deployment')
class DeploymentStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

        self._api_deployment = None
        self._api_connector = None
        self._connector_instance = None

        self.handled_vms_instance_id = set([])

    @property
    def api_deployment(self):
        if self._api_deployment is None:
            self._api_deployment = self.api.get(self.job['targetResource']['href']).data
        return self._api_deployment

    @property
    def api_connector(self):
        if self._api_connector_api is None:
            self._api_connector = self.api.get(connector_name).data
        return self._api_connector

    @property
    def connector_instance(self):
        if self._connector_instance is None:
            self._connector_instance = create_connector_instance(self.api_connector, self.api_credential)
        return self._connector_instance

    def handle_deployment(self):
        api_key = None
        try:
            api_key = self.api_deployment['clientAPIKey']['href']
            self.api.delete(self.api_deployment['clientAPIKey']['href'])
        except Exception as e:
            logging.exception('Something went wrong during cleanup of api key {}: {}.'.format(api_key, e))

        filter_params = 'deployment/href="{}" and (name="instanceid" or name="credential.id")'.format(
            self.api_deployment['id'])
        deployment_params = self.api.cimi_search('deploymentParameters', filter=filter_params,
                                                 select='nodeID,name,value').resources_list

        # Collect nodes info from params
        nodes_ids_cred_dict = defaultdict(dict)
        for dp in deployment_params:
            nodes_ids_cred_dict[dp.data['nodeID']].update({dp.data.get('name'): dp.data.get('value')})

        nodes_info = nodes_ids_cred_dict.values()
        key = lambda node_info: node_info['credential.id']
        nodes_info.sort(key=key)

        for cloud_credential_id, group_of_nodes in groupby(nodes_info, key=key):
            cloud_credential = self.api.get(cloud_credential_id).data
            connector_name = cloud_credential['connector']['href']
            api_connector = self.api.get(connector_name).data
            cred_instance_ids = [node['instanceid'] for node in group_of_nodes]
            logging.info('Stopping following VMs {} for {}.'.format(cred_instance_ids, cloud_credential_id))
            connector_instance.stop(cred_instance_ids)

        id_state = 'deployment-parameter/{}'.format(from_data_uuid(':'.join([self.api_deployment['id'], '', 'ss:state'])))
        self.api.edit(id_state, {'value': 'Done'})
        self.api.edit(self.api_deployment['id'], {'state': 'STOPPED'})

        return 0

    def stop_deployment(self):
        logging.info('Deployment stop job started for {}.'.format(self.api_deployment.get('id')))

        self.job.set_progress(10)

        self.handle_deployment()

        return 10000

    def do_work(self):
        self.stop_deployment()
