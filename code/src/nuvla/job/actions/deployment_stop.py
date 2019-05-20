# -*- coding: utf-8 -*-

import logging

from ..actions import action
from .util.deployment import *


@action('stop_deployment')
class DeploymentStopJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

    def handle_deployment(self, api_deployment):
        api_credential = get_credential(self.api, api_deployment)

        api_infrastructure_service = get_infrastructure_service(self.api, api_credential)

        connector_instance = create_connector_instance(api_infrastructure_service, api_credential)

        filter_params = 'deployment/href="{}" and name="instance-id"'.format(api_deployment['id'])

        deployment_params = self.api.search('deployment-parameter', filter=filter_params,
                                            select='node-id,name,value').resources

        if len(deployment_params) > 0:
            container_id = deployment_params[0].data.get('value')
            logging.info('Stopping following containers {} for {}.'.format(container_id, api_credential['id']))
            if container_id is not None:
                connector_instance.stop([container_id])
            else:

                self.job.set_status_message('Deployment parameter {} doesn\'t have a value!'
                                            .format(deployment_params[0].data.get('id')))
        else:
            self.job.set_status_message('No deployment parameters with containers ids found!')

        self.api.edit(api_deployment['id'], {'state': 'STOPPED'})

    def stop_deployment(self):
        deployment_id = self.job['target-resource']['href']

        api_deployment = self.api.get(deployment_id).data

        logging.info('Deployment stop job started for {}.'.format(deployment_id))

        self.job.set_progress(10)

        try:
            self.handle_deployment(api_deployment)
        except:
            try:
                self.api.edit(deployment_id, {'state': 'ERROR'})
            except:
                pass
            raise

        return 0

    def do_work(self):
        self.stop_deployment()
