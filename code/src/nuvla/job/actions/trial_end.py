# -*- coding: utf-8 -*-

import logging
from ..actions import action

action_name = 'trial_end'

log = logging.getLogger(action_name)


@action(action_name)
class TrialEnd(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def do_work(self):
        resource_target = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(resource_target))
        self.job.set_progress(10)

        customer = self.api.get(resource_target)
        response = self.api.operation(customer, 'trial-end')
        self.job.set_status_message(response.data)

        return 0