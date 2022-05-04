# -*- coding: utf-8 -*-

import logging

from typing import List
from nuvla.api.util.date import nuvla_date, today_start_time, today_end_time
from nuvla.api.util.filter import filter_or, filter_and
from ..job import JOB_QUEUED, JOB_RUNNING, JOB_SUCCESS
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


def build_filter_customers(customer_ids: List[str]) -> str:
    return filter_or([f'customer-id="{cid}"' for cid in customer_ids])


@distribution('trial_end')
class TrialEndJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'trial_end'

    def __init__(self, distributor):
        super(TrialEndJobsDistribution, self).__init__(self.DISTRIBUTION_NAME,
                                                       distributor)
        self.collect_interval = 1800  # 30min
        self._jobs_success_pending = None
        self._ignored_customers_ids = None
        self._start_distribution()

    def list_ignored_customer_ids(self):
        state_filter = filter_or([f'state="{state}"' for state in
                                  [JOB_QUEUED, JOB_SUCCESS, JOB_RUNNING]])
        action_filter = 'action="trial_end"'
        created_filter = f'created>="{nuvla_date(today_start_time())}"' \
                         f' and created<="{nuvla_date(today_end_time())}"'
        filter_job_str = filter_and(
            [created_filter, action_filter, state_filter])
        jobs = self.distributor.api.search(
            'job',
            last=10000,
            select=['id', 'target-resource'],
            filter=filter_job_str).resources
        return [job.data['target-resource']['href'] for job in jobs]

    def trial_doc(self):
        result = self.distributor.api.search('trial').resources
        return result[0] if result else None

    def get_expiration_resource(self):
        expiration = self.trial_doc()
        if expiration is None:
            self.distributor.api.add('trial', {})
            expiration = self.trial_doc()
        return expiration

    def get_trials(self):
        return self.distributor.api.operation(
            self.get_expiration_resource(), 'regenerate') \
            .data.get('expirations', [])

    def list_customer_ids(self):
        return [trial.get('customer') for trial in self.get_trials()
                if trial.get('customer')]

    def search_customers(self, filter_customers):
        return self.distributor.api.search(
            'customer',
            last=10000,
            select=['id'],
            filter=filter_customers).resources

    def get_customers(self):
        customer_filter = build_filter_customers(self.list_customer_ids())
        if customer_filter:
            return self.search_customers(customer_filter)
        else:
            return []

    def trialing_customers_ids(self):
        try:
            return [customer.id for customer in self.get_customers()]
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    @override
    def job_generator(self):
        for customer_id in self.trialing_customers_ids():
            yield {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': customer_id}}
