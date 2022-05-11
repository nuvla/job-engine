# -*- coding: utf-8 -*-

import json
import logging
from ..actions import action

action_name = 'handle_trial_end'

log = logging.getLogger(action_name)


@action(action_name)
class HandleTrialEnd(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def do_work(self):
        payload = json.loads(self.job.get('payload', '{}'))
        customer_id = payload['customer']
        log.info(
            f'Job started for {action_name} for customer id {customer_id}.')
        self.job.set_progress(10)
        response = self.api.hook('handle-trial-end',
                                 {'customer-id': customer_id})
        self.job.set_status_message(response.data)

        return 0
