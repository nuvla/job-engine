# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector, docker_cli_connector
from .nuvla import Deployment, DeploymentParameter
from ..actions import action

from .deployment_start import get_env, application_params_update

action_name = 'update_deployment'

log = logging.getLogger(action_name)


@action(action_name)
class DeploymentUpdateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def update_component(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))

        module_content = Deployment.module_content(deployment)

        # name of the service is the UUID of the deployment in the case of component
        sname = Deployment.uuid(deployment)

        # FIXME: only image update for now
        service = connector.update(sname, image=module_content['image'])

        # immediately update any port mappings that are already available
        ports_mapping = connector.extract_vm_ports_mapping(service)
        self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def update_application(self, deployment):
        """
        FIXME: this is a stub. The function was not tested.
        :param deployment:
        :return:
        """
        raise NotImplementedError('Update of running application is not implemented.')

        connector = connector_factory(docker_cli_connector, self.api, deployment.get('parent'))

        module_content = Deployment.module_content(deployment)

        result, services = connector.update(docker_compose=module_content['docker-compose'],
                                            stack_name=Deployment.uuid(deployment),
                                            env=get_env(deployment),
                                            files=module_content.get('files'))

        self.job.set_status_message(result.stdout.decode('UTF-8'))

        # TODO: update the parameter
        # self.create_deployment_parameter(
        #     deployment_id=Deployment.id(deployment),
        #     user_id=Deployment.owner(deployment),
        #     param_name=DeploymentParameter.HOSTNAME['name'],
        #     param_value=connector.extract_vm_ip(services),
        #     param_description=DeploymentParameter.HOSTNAME['description'])

        application_params_update(self.api_dpl, deployment, services)

    def update_deployment(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            if Deployment.is_component(deployment):
                self.update_component(deployment)
            elif Deployment.is_application(deployment):
                self.update_application(deployment)
        except Exception as ex:
            log.error('Failed to update {0}: {1}'.format(deployment_id, ex))
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
