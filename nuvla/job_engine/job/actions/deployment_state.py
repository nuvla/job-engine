# -*- coding: utf-8 -*-

import logging

from ...connector import docker_service
from nuvla.api.resources import Deployment, DeploymentParameter
from nuvla.api.util.date import utcnow, nuvla_date
from .utils.deployment_utils import (initialize_connector,
                                     DeploymentBase,
                                     get_connector_name,
                                     get_connector_class,
                                     get_env)
from ..actions import action

action_name = 'deployment_state'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentStateJob(DeploymentBase):

    def __init__(self, _, job):
        super().__init__(_, job, log)

    def get_component_state(self):
        connector = initialize_connector(docker_service, self.job,
                                         self.deployment)

        did = Deployment.id(self.deployment)
        # FIXME: at the moment deployment UUID is the service name.
        sname = self.api_dpl.uuid(self.deployment)

        desired = connector.service_replicas_desired(sname)

        tasks = sorted(connector.service_tasks(filters={'service': sname}),
                       key=lambda x: x['CreatedAt'], reverse=True)

        if len(tasks) > 0:
            current_task = tasks[0]
            current_desired = current_task.get('DesiredState')
            current_state = None
            current_error = None
            current_status = current_task.get('Status')
            if current_status is not None:
                current_state = current_status.get('State')
                current_error = current_status.get('Err', "no error")

            if current_desired is not None:
                self.api_dpl.set_parameter_ignoring_errors(
                    did, sname, DeploymentParameter.CURRENT_DESIRED['name'],
                    current_desired)

            if current_state is not None:
                self.api_dpl.set_parameter_ignoring_errors(
                    did, sname, DeploymentParameter.CURRENT_STATE['name'],
                    current_state)

            if current_error is not None:
                self.api_dpl.set_parameter_ignoring_errors(
                    did, sname, DeploymentParameter.CURRENT_ERROR['name'],
                    current_error)

        t_running = list(filter(lambda x:
                                x['DesiredState'] == 'running' and
                                x['Status']['State'] == 'running', tasks))
        t_failed = list(filter(lambda x:
                               x['DesiredState'] == 'shutdown' and
                               x['Status']['State'] == 'failed', tasks))
        t_rejected = list(filter(lambda x:
                                 x['DesiredState'] == 'shutdown' and
                                 x['Status']['State'] == 'rejected', tasks))

        self.api_dpl.set_parameter(did, sname,
                                   DeploymentParameter.CHECK_TIMESTAMP['name'],
                                   nuvla_date(utcnow()))

        self.api_dpl.set_parameter(did, sname,
                                   DeploymentParameter.REPLICAS_DESIRED['name'],
                                   str(desired))

        self.api_dpl.set_parameter(did, sname,
                                   DeploymentParameter.REPLICAS_RUNNING['name'],
                                   str(len(t_running)))

        if len(t_failed) > 0:
            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_NUMBER[
                                           'name'],
                                       str(len(t_failed)))

            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_TIMESTAMP[
                                           'name'],
                                       t_failed[0].get('CreatedAt', ''))

            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_ERR_MSG[
                                           'name'],
                                       t_failed[0].get('Status', {}).get('Err',
                                                                         ''))

            exit_code = str(
                t_failed[0].get('Status', {}).get('ContainerStatus', {}).get(
                    'ExitCode', ''))
            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_EXIT_CODE[
                                           'name'],
                                       exit_code)
        elif len(t_rejected) > 0:
            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_NUMBER[
                                           'name'],
                                       str(len(t_rejected)))

            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_TIMESTAMP[
                                           'name'],
                                       t_rejected[0].get('CreatedAt', ''))

            self.api_dpl.set_parameter(did, sname,
                                       DeploymentParameter.RESTART_ERR_MSG[
                                           'name'],
                                       t_rejected[0].get('Status', {}).get(
                                           'Err', ''))

        # update any port mappings that are available
        services = connector.list(filters={"name": sname})
        if services:
            ports_mapping = connector.extract_vm_ports_mapping(services[0])
            self.api_dpl.update_port_parameters(self.deployment, ports_mapping)

    def get_application_state(self):
        kwargs = {}
        if Deployment.is_compatibility_docker_compose(self.deployment):
            kwargs['compose_file'] = Deployment.module_content(self.deployment)['docker-compose']

        connector_name = get_connector_name(self.deployment)
        connector_class = get_connector_class(connector_name)
        connector = initialize_connector(connector_class, self.job, self.deployment)
        services = connector.get_services(Deployment.uuid(self.deployment),
                                          get_env(self.deployment.data),
                                          **kwargs)

        self.create_update_hostname_output_parameter()
        self.create_update_ips_output_parameters()

        self.application_params_update(services)

    def do_work(self):
        log.info('Job started for {}.'.format(self.deployment_id))
        self.job.set_progress(10)

        try:
            if Deployment.is_component(self.deployment):
                self.get_component_state()
            else:
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
