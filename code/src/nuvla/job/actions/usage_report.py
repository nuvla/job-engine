# -*- coding: utf-8 -*-

import logging
from ..actions import action
from ..util import parse_cimi_date
import stripe

action_name = 'usage_report'

log = logging.getLogger(action_name)


@action(action_name)
class UsageReport(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        config = self.api.get('configuration/nuvla')
        stripe.api_key = config.data.get('stripe-api-key')

    def get_valid_subscription_id(self, customer):
        subscription = self.api.operation(customer, 'get-subscription')
        return subscription.data.get('id')

    def usage_report(self, owner_id, subscription_item_id, nickname):
        query_result = None
        quantity = None

        if nickname == 'nuvlabox':
            nb_ids_filter = ["parent='{}'".format(nb.id) for nb in
                             self.api.search('nuvlabox',
                                             filter="state='COMMISSIONED' and "
                                                    "owner='{}'".format(owner_id),
                                             select='id, nuvlabox-status '
                                             ).resources]
            if nb_ids_filter:
                query_result = self.api.search('nuvlabox-status',
                                               filter="updated > 'now-1h' and "
                                                      "({})".format(' or '.join(nb_ids_filter)),
                                               aggregation="value_count:id", last=0)

        elif nickname == 'deployment':
            dep_filter = "state='STARTED' and owner='{}' and infrastructure-service!=null".format(owner_id)
            nb_ids_filter = ["parent='{}'".format(nb.data.get('infrastructure-service-group')) for nb in
                             self.api.search('nuvlabox', filter="owner='{}'".format(owner_id),
                                             select='id, infrastructure-service-group'
                                             ).resources]
            if nb_ids_filter:
                infra_nb_ids_filter = ["infrastructure-service !='{}'".format(infra.id) for infra in
                                       self.api.search('infrastructure-service',
                                                       filter="subtype='swarm' and ({})".format(
                                                           ' or '.join(nb_ids_filter)),
                                                       select='id').resources]
                if infra_nb_ids_filter:
                    dep_filter += " and {}".format(' and '.join(infra_nb_ids_filter))
            query_result = self.api.search('deployment', filter=dep_filter,
                                           aggregation="value_count:id", last=0)
        elif nickname == 'vpn':
            query_result = self.api.search('credential',
                                           filter="subtype='infrastructure-service-vpn' and "
                                                  "vpn-certificate-owner='{}'".format(owner_id),
                                           aggregation="value_count:id", last=0)

        if query_result is not None:
            quantity = query_result.data.get('aggregations', {}).get('value_count:id', {}).get('value')

        if quantity is not None:
            job_updated_date = parse_cimi_date(self.job.updated)
            stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=int(job_updated_date.timestamp()))

    def do_work(self):
        customer_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(customer_id))
        customer = self.api.get(customer_id)

        self.job.set_progress(10)

        owner_id = customer.data['parent']

        subscription_id = self.get_valid_subscription_id(customer)

        if subscription_id:
            try:
                subscription_items = stripe.SubscriptionItem.list(subscription=subscription_id)
                for item in subscription_items.data:
                    price_item = item.price
                    usage_type = price_item.recurring.usage_type
                    nickname = price_item.nickname
                    if usage_type == 'metered' and nickname in ['nuvlabox', 'vpn', 'deployment']:
                        self.usage_report(owner_id, item.id, nickname)
            except Exception as ex:
                log.error('Failed to {0} {1}: {2}'.format(self.job['action'], customer_id, ex))
                raise ex

        return 0
