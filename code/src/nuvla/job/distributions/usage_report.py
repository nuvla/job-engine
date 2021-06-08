# -*- coding: utf-8 -*-

import logging

from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('usage_report')
class UsageReportJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'usage_report'

    def __init__(self, distributor):
        super(UsageReportJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 1800
        self._start_distribution()

    def customers(self):
        try:
            return self.distributor.api.search('customer', select='id').resources
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    def deployments(self):
        try:
            return self.distributor.api.search('deployment', filter="module/price != null"
                                                                    " and state = 'STARTED'"
                                                                    " and subscription-id != null",
                                               select='id,module').resources
        except Exception as ex:
            logging.error(f'Failed to search for deployments: {ex}')
            return []

    def job_exists(self, job):
        filters = f"(state='QUEUED' or state='RUNNING')" \
                  f" and action='{job['action']}'" \
                  f" and target-resource/href='{job['target-resource']['href']}'"
        jobs = self.distributor.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        for resource in self.customers() + self.deployments():
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job
