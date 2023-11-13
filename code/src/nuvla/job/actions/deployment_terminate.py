# -*- coding: utf-8 -*-

import logging

from .deployment_stop import DeploymentStopJob
from ..actions import action

action_name = 'terminate_deployment'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentTerminateJob(DeploymentStopJob):

    def terminate_deployment(self):
        log.info('Job started for {}.'.format(self.deployment_id))
        self.job.set_progress(10)
        self.try_handle_raise_exception(log)
        self.api_dpl.set_state_stopped(self.deployment_id)
        self.api.delete(self.deployment_id)
        self.try_delete_deployment_credentials(self.deployment_id)
        return 0

    def do_work(self):
        return self.terminate_deployment()
