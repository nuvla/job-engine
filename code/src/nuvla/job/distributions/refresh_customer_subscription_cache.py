# -*- coding: utf-8 -*-

import logging

from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('refresh_customer_subscription_cache')
class RefreshCustomerSubscriptionCache(DistributionBase):
    DISTRIBUTION_NAME = 'refresh_customer_subscription_cache'

    def __init__(self, distributor):
        super(RefreshCustomerSubscriptionCache, self).__init__(
            self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 3600
        self._start_distribution()

    def customers(self):
        try:
            return self.distributor.api.search(
                'customer',
                filter='subscription-id!=null',
                select='id,operations',
                last=10000).resources
        except Exception as ex:
            logging.error(f'Failed to search for customers: {ex}')
            return []

    @override
    def job_generator(self):
        # we don't generate a job because it's a simple action call
        for resource in self.customers():
            self.distributor.api.operation(resource, 'get-subscription')
            logging.info(f'Refresh {resource.id}')
        return []
