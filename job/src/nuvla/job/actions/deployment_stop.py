# -*- coding: utf-8 -*-

from __future__ import print_function

import logging

from ..util import create_connector_instance
from ..actions import action


@action('stop_deployment')
class DeploymentStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

        self.handled_vms_instance_id = set([])

    @staticmethod
    def connector_instance(api_infrastructure_service, api_credential, api_endpoint):
        return create_connector_instance(api_infrastructure_service, api_credential, api_endpoint)

    def handle_deployment(self, api_deployment):
        credential_id = api_deployment['credential-id']
        if credential_id is None:
            raise ValueError("Credential id is not set!")

        infrastructure_service_id = api_deployment['infrastructure-service-id']
        if infrastructure_service_id is None:
            raise ValueError("Infrastructure service id is not set!")

        api_credential = self.api.get(credential_id).data

        api_infrastructure_service = self.api.get(infrastructure_service_id).data

        connector_instance = DeploymentStopJob.connector_instance(api_infrastructure_service, api_credential,
                                                                  self.api.endpoint)

        filter_params = 'deployment/href="{}" and name="instance-id"'.format(api_deployment['id'])

        deployment_params = self.api.search('deployment-parameter', filter=filter_params,
                                            select='node-id,name,value').resources

        instance_id = deployment_params[0].data['value']
        logging.info('Stopping following VMs {} for {}.'.format(instance_id, api_credential.id))
        connector_instance.stop([instance_id])

        self.api.edit(api_deployment['id'], {'state': 'STOPPED'})

        return 0

    def stop_deployment(self):
        deployment_id = self.job['targetResource']['href']

        api_deployment = self.api.get(deployment_id).data

        logging.info('Deployment stop job started for {}.'.format(deployment_id))

        self.job.set_progress(10)

        self.handle_deployment(api_deployment)

        return 10000

    def do_work(self):
        self.stop_deployment()
