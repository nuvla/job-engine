# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from nuvla.connector import connector_factory, docker_connector, docker_cli_connector
from .deployment import Deployment, DeploymentParameter
from ..actions import action
from .deployment_start import application_params_update

action_name = 'deployment_state'

log = logging.getLogger(action_name)


def utcnow():
    return datetime.utcnow().isoformat('T', timespec='milliseconds') + 'Z'


@action(action_name)
class DeploymentStateJob(object):

    def __init__(self, executor, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    def get_component_state(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))
        did = Deployment.id(deployment)
        # FIXME: at the moment deployment UUID is the service name.
        sname = self.api_dpl.uuid(deployment)

        desired = connector.service_replicas_desired(sname)

        tasks = sorted(connector.service_tasks(filters={'service': sname}),
                       key=lambda x: x['CreatedAt'], reverse=True)

        t_running = list(filter(lambda x: x['DesiredState'] == 'running', tasks))
        t_failed = list(filter(lambda x:
                               x['DesiredState'] == 'shutdown' and
                               x['Status']['State'] == 'failed', tasks))
        t_rejected = list(filter(lambda x:
                                 x['DesiredState'] == 'shutdown' and
                                 x['Status']['State'] == 'rejected', tasks))

        self.api_dpl.set_parameter(did, sname, DeploymentParameter.CHECK_TIMESTAMP['name'],
                                   utcnow())

        self.api_dpl.set_parameter(did, sname, DeploymentParameter.REPLICAS_DESIRED['name'],
                                   str(desired))

        self.api_dpl.set_parameter(did, sname, DeploymentParameter.REPLICAS_RUNNING['name'],
                                   str(len(t_running)))

        if len(t_failed) > 0:
            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_NUMBER['name'],
                                       str(len(t_failed)))

            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_TIMESTAMP['name'],
                                       t_failed[0].get('CreatedAt', ''))

            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_ERR_MSG['name'],
                                       t_failed[0].get('Status', {}).get('Err', ''))

            exit_code = str(
                t_failed[0].get('Status', {}).get('ContainerStatus', {}).get('ExitCode', ''))
            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_EXIT_CODE['name'],
                                       exit_code)
        elif len(t_rejected) > 0:
            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_NUMBER['name'],
                                       str(len(t_rejected)))

            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_TIMESTAMP['name'],
                                       t_rejected[0].get('CreatedAt', ''))

            self.api_dpl.set_parameter(did, sname, DeploymentParameter.RESTART_ERR_MSG['name'],
                                       t_rejected[0].get('Status', {}).get('Err', ''))

        # update any port mappings that are available
        services = connector.list(filters={"name": sname})
        if services:
            ports_mapping = connector.extract_vm_ports_mapping(services[0])
            self.api_dpl.update_port_parameters(deployment, ports_mapping)

    def get_application_state(self, deployment):
        connector = connector_factory(docker_cli_connector, self.api,
                                      deployment.get('parent'))
        stack_name = Deployment.uuid(deployment)
        services = connector.stack_services(stack_name)
        application_params_update(self.api_dpl, deployment, services)

    def do_work(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        if Deployment.is_component(deployment):
            self.get_component_state(deployment)
        elif Deployment.is_application(deployment):
            self.get_application_state(deployment)

        return 0
