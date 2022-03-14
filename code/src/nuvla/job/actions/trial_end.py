# -*- coding: utf-8 -*-

import logging
from ..actions import action
from ..util import parse_cimi_date
import stripe

action_name = 'trial_end'

log = logging.getLogger(action_name)


@action(action_name)
class TrialEnd(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        config = self.api.get('configuration/nuvla')
        stripe.api_key = config.data.get('stripe-api-key')

    def do_work(self):
        resource_target = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(resource_target))
        self.job.set_progress(10)

        customer = self.api.get(resource_target)
        response = self.api.operation(customer, 'trial-end')
        self.job.set_status_message(response.data)

        return 0
