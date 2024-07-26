# -*- coding: utf-8 -*-
import logging

from ..actions import action
from .utils.deployment_utils import DeploymentBaseStartUpdate

action_name = 'update_deployment'


@action(action_name, True)
class DeploymentUpdateJob(DeploymentBaseStartUpdate):

    def __init__(self, job):
        super().__init__(
            action_name,
            job,
            logging.getLogger(action_name))
