# -*- coding: utf-8 -*-

import logging

from nuvla.api.resources import Deployment
from .utils.deployment_utils import (initialize_connector,
                                     DeploymentBase,
                                     get_connector_name,
                                     get_connector_module,
                                     CONNECTOR_KIND_HELM,
                                     get_env)
from ..actions import action

action_name = 'deployment_state'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentStateJob(DeploymentBase):

    def __init__(self, job):
        super().__init__(job, log)

    def get_application_state(self):
        kwargs = {}
        if Deployment.is_compatibility_docker_compose(self.deployment):
            kwargs['compose_file'] = Deployment.module_content(self.deployment)['docker-compose']

        connector_name = get_connector_name(self.deployment)
        connector_module = get_connector_module(connector_name)
        connector = initialize_connector(connector_module, self.job,
                                         self.deployment)
        services = connector.get_services(Deployment.uuid(self.deployment),
                                          get_env(self.deployment.data),
                                          **kwargs)

        self.create_update_hostname_output_parameter()
        self.create_update_ips_output_parameters()

        self.application_params_update(services)

        if connector_name == CONNECTOR_KIND_HELM:
            namespace = Deployment.uuid(self.deployment.data)
            release_name = connector.helm_release_name(namespace)
            release = connector.get_helm_release(release_name, namespace=namespace)
            self.app_helm_release_params_update(release)

    def do_work(self):
        log.info('Job started for {}.'.format(self.deployment_id))
        self.job.set_progress(10)

        try:
            self.get_application_state()
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'],
                                                      self.deployment_id, ex))
            self.job.set_status_message(repr(ex))
            raise ex

        return 0


@action(action_name + '_10', True)
class DeploymentStateJob10(DeploymentStateJob):
    pass


@action(action_name + '_60', True)
class DeploymentStateJob60(DeploymentStateJob):
    pass
