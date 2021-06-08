# -*- coding: utf-8 -*-

import logging
from copy import copy
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase

LAST = 10000


@distribution('subscriptions_manager')
class SubscriptionsManager(DistributionBase):
    DISTRIBUTION_NAME = 'subscriptions_manager'

    def __init__(self, distributor):
        super(SubscriptionsManager, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 30
        self._start_distribution()

    @override
    def job_generator(self):
        # no job generation
        # TODO: optimisation - consider caching the last check time and
        #  searching for the configs updated from e.g. (last check time - 15min).
        for subs_conf in self._get_subscription_configs():
            res_subs_ids = self._get_individual_subscriptions(subs_conf)
            res_ids = self._resources_by_filter(subs_conf)
            for v in res_ids.difference(res_subs_ids):
                self._add_subscription(subs_conf, v)
            for v in set(res_subs_ids) - res_ids:
                self._delete_subscription(res_subs_ids[v])
        return []

    def _get_subscription_configs(self) -> dict:
        subs_configs = self.distributor.api.search('subscription-config', last=LAST)
        logging.info(f'Subscription configs number: {subs_configs.count}')
        for r in subs_configs.resources:
            yield r.data

    def _add_subscription(self, subs_conf: dict, r_id):
        subs = copy(subs_conf)
        subs['parent'] = subs_conf['id']
        subs['resource-id'] = r_id
        result = self.distributor.api.add("subscription", subs).data
        if result['status'] != 201:
            logging.error(f'Failed adding subscription for {r_id} with: {result}')
        else:
            logging.debug(f'Added subscription for {r_id}')

    def _delete_subscription(self, subs_id):
        result = self.distributor.api.delete(subs_id).data
        if result['status'] != 200:
            logging.error(f'Failed deleting {subs_id} with: {result}')
        else:
            logging.debug(f'Deleted subscription {subs_id}')

    def _resources_by_filter(self, subs_conf):
        owner = subs_conf.get('acl').get('owners')[0]
        flt = f"acl/owners='{owner}' or acl/view-data='{owner}'"
        rf = subs_conf.get('resource-filter') or None
        if rf:
            flt = f'({flt}) and {rf}'
        resources = self.distributor.api.search(subs_conf.get('resource-kind'),
                                                filter=flt, last=LAST)
        return set(map(lambda x: x.id, resources))

    def _get_individual_subscriptions(self, subs_conf):
        filters = f"parent = '{subs_conf.get('id')}'"
        select = 'id,resource-id'
        subs = self.distributor.api.search('subscription', filter=filters, select=select, last=LAST)
        sub_res = {}
        for s in map(lambda x: x.data, subs.resources):
            sub_res[s.get('resource-id')] = s.get('id')
        return sub_res
