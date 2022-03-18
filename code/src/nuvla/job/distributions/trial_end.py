# -*- coding: utf-8 -*-

import logging

from typing import List, Optional
from nuvla.api.util.date import nuvla_date, today_start_time, today_end_time
from ..job import JOB_QUEUED, JOB_RUNNING, JOB_SUCCESS
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


def filter_join(list_comparison: List[str], join_logic: str = 'or') \
        -> Optional[str]:
    list_comparison_filtered = [x for x in list_comparison if x is not None]
    if list_comparison_filtered:
        separator = f' {join_logic} '
        result = separator.join(list_comparison_filtered)
        return f'({result})' if len(list_comparison_filtered) > 1 else result


def filter_or(list_comparison: List[str]) -> str:
    return filter_join(list_comparison, 'or')


def filter_and(list_comparison: List[str]) -> str:
    return filter_join(list_comparison, 'and')


def build_filter_customers(stripe_customer_ids_trialing: List[str],
                           customer_ids_ignored: List[str]) -> str:
    filter_trialing_customer = filter_or(
        [f'customer-id="{cid}"' for cid in stripe_customer_ids_trialing])
    filter_customer_ids_ignored = filter_or(
        [f'id!="{customer_id}"' for customer_id in customer_ids_ignored])
    return filter_and([filter_trialing_customer, filter_customer_ids_ignored])


@distribution('trial_end')
class TrialEndJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'trial_end'

    def __init__(self, distributor):
        super(TrialEndJobsDistribution, self).__init__(self.DISTRIBUTION_NAME,
                                                       distributor)
        self.collect_interval = 21600  # 6h
        self._jobs_success_pending = None
        self._ignored_customers_ids = None
        self._trials = None
        # TODO error prone, should be called explicitly
        # from distributor base class
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

    @property
    def trials(self):
        if self._trials is None:
            self._trials = self.get_trials()
        return self._trials

    def list_customer_ids(self):
        return [trial.get('customer') for trial in self.trials
                if trial.get('customer')]

    def search_customers(self, filter_customers):
        return self.distributor.api.search(
            'customer',
            last=10000,
            select=['id'],
            filter=filter_customers).resources

    def get_customers(self):
        stripe_customer_ids_trialing = self.list_customer_ids()
        customer_ids_ignored = self.list_ignored_customer_ids()
        customer_filter = build_filter_customers(
            stripe_customer_ids_trialing,
            customer_ids_ignored)
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
