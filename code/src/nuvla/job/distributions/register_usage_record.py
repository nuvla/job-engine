# -*- coding: utf-8 -*-

import logging

from nuvla.api.util.filter import filter_or, filter_and
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


def customer_is_group(customer):
    return customer.data['parent'].startswith('group/')


@distribution('register_usage_record')
class RegisterUsageRecordJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'register_usage_record'

    def __init__(self, distributor):
        super(RegisterUsageRecordJobsDistribution, self).__init__(
            self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 1800
        self._start_distribution()

    def customers(self):
        try:
            return self.distributor.api.search(
                'customer',
                filter='subscription-id!=null',
                select='id, parent',
                last=10000
            ).resources
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    def subgroups(self, customers):
        try:
            ids = [f"parents='{c.data['parent']}'" for c in customers
                   if c.data['parent'].startswith('group/')]
            return self.distributor.api.search(
                'group',
                filter=filter_or(ids),
                select='id',
                last=10000
            ).resources
        except Exception as ex:
            logging.error(f'Failed to search for subgroups: {ex}')
            return []

    def deployments(self):
        try:
            return self.distributor.api.search(
                'deployment',
                filter=filter_and(["module/price != null",
                                   "state = 'STARTED'",
                                   "subscription-id != null"]),
                select='id, module',
                last=10000
            ).resources
        except Exception as ex:
            logging.error(f'Failed to search for deployments: {ex}')
            return []

    def job_exists(self, job):
        jobs = self.distributor.api.search(
            'job',
            filter=filter_and(
                [filter_or(["state='QUEUED'", "state='RUNNING'"]),
                 f"action='{job['action']}'",
                 f"target-resource/href='{job['target-resource']['href']}'"]),
            last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        customers = self.customers()
        subgroups = self.subgroups(customers)
        deployments = self.deployments()
        logging.info(f'Customers count: {len(customers)}')
        logging.info(f'Subgroups count: {len(subgroups)}')
        logging.info(f'Deployments count: {len(deployments)}')
        for resource in customers + subgroups + deployments:
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job
