#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from copy import copy
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class SubscriptionsManager(Distributor):
    ACTION_NAME = 'subscriptions_manager'

    def __init__(self):
        super(SubscriptionsManager, self).__init__()
        self.collect_interval = 30

    @override
    def _get_jobs_type(self):
        return SubscriptionsManager.ACTION_NAME

    @override
    def job_generator(self):
        # no job generation
        for subs_conf in self._get_subscription_configs():
            res_subs_ids = self._get_individual_subscriptions(subs_conf)
            res_ids = self._resources_by_filter(subs_conf)
            for v in res_ids.difference(res_subs_ids):
                self._add_subscription(subs_conf, v)
            for v in set(res_subs_ids) - res_ids:
                self._delete_subscription(res_subs_ids[v])
        return []

    def _get_subscription_configs(self) -> dict:
        last = 10000
        subs_configs = self.api.search('subscription-config', last=last)
        logging.info(f'Subscription configs number: {subs_configs.count}')
        for r in subs_configs.resources:
            yield r.data

    def _add_subscription(self, subs_conf: dict, r_id):
        subs = copy(subs_conf)
        subs['parent'] = subs_conf['id']
        subs['resource-id'] = r_id
        result = self.api.add("subscription", subs).data
        if result['status'] != 201:
            logging.error(f'Failed adding subscription for {r_id} with: {result}')
        else:
            logging.debug(f'Added subscription for {r_id}')

    def _delete_subscription(self, subs_id):
        result = self.api.delete(subs_id).data
        if result['status'] != 200:
            logging.error(f'Failed deleting {subs_id} with: {result}')
        else:
            logging.debug(f'Deleted subscription {subs_id}')

    def _resources_by_filter(self, subs_conf):
        last = 10000
        resources = self.api.search(subs_conf.get('resource-kind'),
                                    filter=subs_conf.get('resource-filter') or None, last=last)
        return set(map(lambda x: x.id, resources))

    def _get_individual_subscriptions(self, subs_conf):
        filters = f"parent = '{subs_conf.get('id')}'"
        select = 'id,resource-id'
        last = 10000
        subs = self.api.search('subscription', filter=filters, select=select, last=last)
        subs_all = map(lambda x: x.data, subs.resources)
        sub_res = {}
        for s in subs_all:
            sub_res[s.get('resource-id')] = s.get('id')
        return sub_res


if __name__ == '__main__':
    main(SubscriptionsManager)
