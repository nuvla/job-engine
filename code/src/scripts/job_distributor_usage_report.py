#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class UsageReportJobsDistributor(Distributor):
    ACTION_NAME = 'usage_report'

    def __init__(self):
        self.collect_interval = 1800
        super(Distributor, self).__init__()
        self.collect_interval = self.args.interval

    def _set_command_specific_options(self, parser):
        hmsg = 'Jobs distribution interval in seconds (default: {})' \
            .format(self.collect_interval)
        parser.add_argument('--interval', dest='interval', metavar='INTERVAL',
                            default=self.collect_interval, type=int, help=hmsg)

    def customers(self):
        try:
            return self.api.search('customer', select='id').resources
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')

    def deployments(self):
        try:
            return self.api.search('deployment', filter="module/price != null"
                                                        " and state = 'STARTED'"
                                                        " and subscription-id != null",
                                   select='id,module').resources
        except Exception as ex:
            logging.error(f'Failed to search for deployments: {ex}')

    def job_exists(self, job):
        filters = f"(state='QUEUED' or state='RUNNING')" \
                  f" and action='{job['action']}'" \
                  f" and target-resource/href='{job['target-resource']['href']}'"
        jobs = self.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        for resource in self.customers() + self.deployments():
            job = {'action': self._get_jobs_type(),
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job

    @override
    def _get_jobs_type(self):
        return self.ACTION_NAME


if __name__ == '__main__':
    main(UsageReportJobsDistributor)
