# -*- coding: utf-8 -*-

import logging
from ..actions import action
import stripe

action_name = 'usage_report'

log = logging.getLogger(action_name)

QUERY_AGG = {'nuvlabox': {
    'resource': 'nuvlabox',
    'filter': 'owner="%s"',
    'aggregation': ''}}


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
        if nickname == 'nuvlabox':
            query_result = self.api.search('nuvlabox',
                                           filter="state='COMMISSIONED' and "
                                                  "owner='%s'".format(owner_id),
                                           aggregation="value_count:id")
        elif nickname == 'deployment':
            query_result = self.api.search('deployment',
                                           filter="state='STARTED' and "
                                                  "owner='%s'".format(owner_id),
                                           aggregation="value_count:id")
        elif nickname == 'vpn':
            query_result = self.api.search('credential',
                                           filter="subtype='infrastructure-service-vpn' and "
                                                  "vpn-certificate-owner='%s'".format(owner_id),
                                           aggregation="value_count:id")

        quantity = query_result.data.get('aggregations', {}).get('value_count:id').get('value')

        if quantity:
            self.stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=quantity,
                timestamp=1571252444)

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
                    plan_item = item.plan
                    usage_type = plan_item.usage_type
                    nickname = plan_item.nickname
                    if usage_type == 'metered' and nickname in ['nuvlabox', 'vpn', 'deployment']:
                        self.usage_report(owner_id, item.id, nickname)
            except Exception as ex:
                log.error('Failed to {0} {1}: {2}'.format(self.job['action'], customer_id, ex))
                raise ex

        return 0
