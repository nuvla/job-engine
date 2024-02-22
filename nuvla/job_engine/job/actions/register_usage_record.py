# -*- coding: utf-8 -*-

import logging
from ..actions import action

action_name = 'register_usage_record'

log = logging.getLogger(action_name)


@action(action_name)
class RegisterUsageRecord(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def do_work(self):
        resource_href = self.job['target-resource']['href']
        log.info('Job started for {}.'.format(resource_href))
        log.info(
            f'Job started for {action_name} for resource href {resource_href}.')
        self.job.set_progress(10)
        response = self.api.hook('register-usage-record',
                                 {'resource-href': resource_href})

        self.job.set_status_message(response.data)

        errors_count = len(response.data.get('errors', []))

        return 1 if errors_count > 0 else 0
