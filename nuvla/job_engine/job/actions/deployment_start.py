# -*- coding: utf-8 -*-
import logging

from ..util import override
from ..actions import action
from .utils.deployment_utils import (get_connector_name,
                                     CONNECTOR_KIND_HELM,
                                     DeploymentBaseStartUpdate)

action_name = 'start_deployment'

# TODO: The implementation is the same as in DeploymentUpdateJob. Refactor!


@action(action_name, True)
class DeploymentStartJob(DeploymentBaseStartUpdate):

    def __init__(self, job):
        super().__init__(job, logging.getLogger(action_name))

    def start_application(self):
        deployment = self.deployment.data
        connector_name = get_connector_name(deployment)
        connector = self._get_connector(deployment, connector_name)

        kwargs = self._get_action_kwargs(deployment)
        result, services, extra = connector.start(**kwargs)
        if extra and connector_name == CONNECTOR_KIND_HELM:
            # FIXME: maybe this can be done as callback to the connector start
            #  method?
            self.app_helm_release_params_update(extra)
        if result:
            self.job.set_status_message(result)

        self.application_params_update(services)

        self.job.set_progress(90)

    @override
    def handle_deployment(self):
        self.create_user_output_params()
        self.start_application()

    def start_deployment(self):
        self.log.info(f'{action_name} job started for {self.deployment_id}.')

        self.job.set_progress(10)

        self.try_handle_raise_exception()

        self.api_dpl.set_state_started(self.deployment_id)

        return 0

    def do_work(self):
        return self.start_deployment()
