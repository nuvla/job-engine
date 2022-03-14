# -*- coding: utf-8 -*-

import logging

from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


def list_subscription_ids(trials):
    return [trial.get('id') for trial in trials if trial.get('id')]


def build_filter_customers(subscription_ids):
    return ' or '.join([f'subscription-id="{subscription_id}"' for subscription_id in subscription_ids])


@distribution('trial_end')
class TrialEndJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'trial_end'

    def __init__(self, distributor):
        super(TrialEndJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 30  # 30s
        self._start_distribution()

    def search_customers(self, filter_customers):
        return self.distributor.api.search(
            'customer',
            last=10000,
            select=['id'],
            filter=filter_customers).resources

    def get_customers(self, trials):
        customer_filter = build_filter_customers(list_subscription_ids(trials))
        if customer_filter:
            return self.search_customers(customer_filter)
        else:
            return []

    def get_trials(self):
        expiration = self.distributor.api.get('trial/expiration')
        return self.distributor.api.operation(expiration, 'regenerate').data.get('expirations', [])

    def trialing_customers(self):
        try:
            return self.get_customers(self.get_trials())
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    def job_exists(self, job):
        filters = f"(state='QUEUED' or state='RUNNING')" \
                  f" and action='{job['action']}'" \
                  f" and target-resource/href='{job['target-resource']['href']}'"
        jobs = self.distributor.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        for resource in self.trialing_customers():
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job
