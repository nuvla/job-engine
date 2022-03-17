# -*- coding: utf-8 -*-

import logging

from nuvla.api.util.date import cimi_date, today_start_time, today_end_time
from ..job import JOB_QUEUED, JOB_RUNNING, JOB_SUCCESS
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


def build_filter_customers(subscription_ids):
    return ' or '.join([f'subscription-id="{subscription_id}"'
                        for subscription_id in subscription_ids])


@distribution('trial_end')
class TrialEndJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'trial_end'

    def __init__(self, distributor):
        super(TrialEndJobsDistribution, self) \
            .__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 21600  # 6h
        self._start_distribution()
        self._ignored_customers_ids = None
        self._trials = None

    def get_ignored_customers_ids(self):
        state_filter = '(' + \
                       ' or '.join([f'state="{state}"' for state in
                                    [JOB_QUEUED, JOB_SUCCESS, JOB_RUNNING]]) \
                       + ')'
        action_filter = 'action="trial-end"'
        created_filter = f'created>="{cimi_date(today_start_time())}"' \
                         f' and created<={cimi_date(today_end_time())}'
        filter_str = ' and '.join([created_filter, action_filter, state_filter])
        jobs = self.distributor.api.search(
            'job',
            last=10000,
            select=['id', 'state', 'target-resource'],
            filter=filter_str).resources
        return [job.data['target-resource']['href'] for job in jobs]

    @property
    def ignored_customers_ids(self):
        if self._ignored_customers_ids is None:
            self._ignored_customers_ids = self.get_ignored_customers_ids()
        return self._ignored_customers_ids

    def is_ignored_customer(self, customer_id: str):
        return customer_id in self.ignored_customers_ids

    def get_trials(self):
        # TODO create trial document if not existing
        expiration = self.distributor.api.get('trial/expiration')
        return self.distributor.api.operation(expiration, 'regenerate') \
            .data.get('expirations', [])

    @property
    def trials(self):
        if self._trials is None:
            self._trials = self.get_trials()
        return self._trials

    def list_subscription_ids(self):
        return [trial.get('id') for trial in self.trials
                if trial.get('id') and not self.is_ignored_customer(
                trial.get('customer'))]

    def search_customers(self, filter_customers):
        return self.distributor.api.search(
            'customer',
            last=10000,
            select=['id'],
            filter=filter_customers).resources

    def get_customers(self):
        customer_filter = build_filter_customers(self.list_subscription_ids())
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
