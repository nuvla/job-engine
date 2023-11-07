# -*- coding: utf-8 -*-

import logging

from nuvla.api.util.filter import filter_and
from ..job import JOB_QUEUED, JOB_RUNNING
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


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
                filter=filter_and(['subscription-id!=null',
                                   'subscription-cache/status!="canceled"']),
                select='id, parent',
                last=10000).resources
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    def subgroups(self, customers):
        try:
            ids = [c.data['parent'] for c in customers
                   if c.data['parent'].startswith('group/')]
            if ids:
                return self.distributor.api.search(
                    'group',
                    filter=f'parents={ids}',
                    select='id',
                    last=10000).resources
            else:
                return []
        except Exception as ex:
            logging.error(f'Failed to search for subgroups: {ex}')
            return []

    def job_exists(self, job):
        jobs = self.distributor.api.search(
            'job',
            filter=filter_and(
                [f'state={[JOB_RUNNING, JOB_QUEUED]}',
                 f"action='{job['action']}'",
                 f"target-resource/href='{job['target-resource']['href']}'"]),
            last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        customers = self.customers()
        subgroups = self.subgroups(customers)
        logging.info(f'Customers count: {len(customers)}')
        logging.info(f'Subgroups count: {len(subgroups)}')
        for resource in customers + subgroups:
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job
