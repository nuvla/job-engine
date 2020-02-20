# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from .nuvla import Deployment
from ..actions import action

action_name = 'update_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentUpdateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def private_registries_auth(self, deployment):
        registries_credentials = deployment.get('registries-credentials')
        if registries_credentials:
            list_cred_infra = []
            for registry_cred in registries_credentials:
                credential = self.api.get(registry_cred).data
                infra_service = self.api.get(credential['parent']).data
                registry_auth = {'username': credential['username'],
                                 'password': credential['password'],
                                 'serveraddress': infra_service['endpoint'].replace('https://', '')}
                list_cred_infra.append(registry_auth)
            return list_cred_infra
        else:
            return None

    def update_component(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))

        module_content = Deployment.module_content(deployment)

        # name of the service is the UUID of the deployment in the case of component
        sname = Deployment.uuid(deployment)

        registries_auth = self.private_registries_auth(deployment)

        # FIXME: only image update for now
        service = connector.update(sname, image=module_content['image'],
                                   registries_auth=registries_auth)

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(service)
        self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def update_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            if Deployment.is_component(deployment):
                self.update_component(deployment)
            elif Deployment.is_application(deployment):
                raise NotImplementedError('Update of running application is not implemented.')
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], deployment_id, ex))
            try:
                self.job.set_status_message(repr(ex))
                self.api_dpl.set_state_error(deployment_id)
            except Exception as ex_state:
                log.error('Failed to set error state for {0}: {1}'.format(deployment_id, ex_state))

            raise ex

        self.api_dpl.set_state_started(deployment_id)

        return 0

    def do_work(self):
        return self.update_deployment()
