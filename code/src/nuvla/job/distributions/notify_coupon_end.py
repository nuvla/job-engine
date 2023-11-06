# -*- coding: utf-8 -*-

import json
import logging
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('notify_coupon_end')
class NotifyCouponEndJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'notify_coupon_end'

    def __init__(self, distributor):
        super(NotifyCouponEndJobsDistribution, self).__init__(
            self.DISTRIBUTION_NAME,
            distributor)
        self.collect_interval = 3600  # 1 hour
        self._start_distribution()

    def list_coupons(self):
        return self.distributor.api.hook('list-coupons').data

    def coupon_ids(self):
        try:
            return [coupon.get('id') for coupon in self.list_coupons() if
                    coupon.get('id')]
        except Exception as ex:
            logging.error(f'Failed to list coupons: {ex}')
            return []

    def job_exists(self, job):
        filters = "(state='QUEUED' or state='RUNNING')" \
                  " and action='{0}'" \
                  " and payload='{1}'" \
            .format(job['action'], job['payload'])
        jobs = self.distributor.api.search('job', filter=filters, last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        for coupon_id in self.coupon_ids():
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': 'hook/notify-coupon-end'},
                   'payload': json.dumps({'coupon': coupon_id})}
            if not self.job_exists(job):
                yield {'action': self.DISTRIBUTION_NAME,
                       'target-resource': {'href': 'hook/notify-coupon-end'},
                       'payload': json.dumps({'coupon': coupon_id})}
