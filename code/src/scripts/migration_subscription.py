#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import time

import stripe
from nuvla.api import Api
from nuvla.api.util.date import utcnow

stripe.api_key = "sk_test_"

product_to_delete = ['prod_HYV40L9kxhkxjF', 'prod_HYV8zAoAKMsp5q',
                     'prod_HYVgsIbwoFh8hi']
product_to_replace = ['prod_HYVCzR5PYSPFLO']
product_nuvla_edge = 'price_1LAYnzHG9PNMTNBOTrWO9dZg'

dry_run = False

number_of_error = 0


def print_section(text):
    print(
        '================================================================================================================================')
    print(text)
    print(
        '================================================================================================================================')


def print_subsection(text):
    print('\t' + text)
    print(
        '--------------------------------------------------------------------------------------------------------------------------------')


def print_nuvla_customer(customer):
    print_subsection(f"customer: {customer.id} "
                     f"subscription: {customer.data['subscription-id']}")


def loop_on_customers(customers, fn):
    for customer in customers:
        fn(customer)


def print_subscription_item(subscription_item):
    product_id = subscription_item.price.product
    product = stripe.Product.retrieve(product_id)
    text = f'Product {product_id} {product.name}'
    if product_id in product_to_replace:
        usage_record_summaries = \
            stripe.SubscriptionItem.list_usage_record_summaries(
                subscription_item.id, limit=1).data[0]
        total_usage = usage_record_summaries.total_usage if usage_record_summaries.invoice is None else 0
        text += f' - Current total usage is: {total_usage}'
    if product_id not in product_to_replace + product_to_delete:
        text += f"\n\t***ERROR*** This product is not expected!"
        global number_of_error
        number_of_error += number_of_error
    print_subsection(text)


def migrate_subscription_item(subscription_id, subscription_item):
    product_id = subscription_item.price.product
    if product_id in product_to_replace:
        usage_record_summaries = \
            stripe.SubscriptionItem.list_usage_record_summaries(
                subscription_item.id, limit=1).data[0]
        total_usage = stripe.SubscriptionItem.list_usage_record_summaries(
            subscription_item.id, limit=1).data[
            0].total_usage if usage_record_summaries.invoice is None else 0
        new_id = stripe.SubscriptionItem.create(
            subscription=subscription_id,
            price=product_nuvla_edge,
            proration_behavior='none').id
        stripe.SubscriptionItem.create_usage_record(new_id,
                                                    )
        timestamp = utcnow().replace(hour=0, minute=0, second=0,
                                     microsecond=0).timestamp()
        print(timestamp)
        stripe.SubscriptionItem.create_usage_record(
            new_id,
            quantity=total_usage,
            action='set',
            timestamp=int(timestamp))
    # if product_id in product_to_delete + product_to_replace:
    #     stripe.SubscriptionItem.delete(subscription_item,
    #                                    proration_behavior='none')


def migrate_subscription(customer):
    # subscription = stripe.Subscription.retrieve(customer.data['subscription-id'])
    # print(subscription)
    subscription_items = stripe.SubscriptionItem.list(
        subscription=customer.data['subscription-id'])
    subscription_id = customer.data['subscription-id']
    # upcoming_invoice = stripe.Invoice.upcoming(subscription=subscription_id)
    # print(upcoming_invoice)
    print_section(f'Migrate subscription {subscription_id}')
    [print_subscription_item(subscription_item)
     for subscription_item in subscription_items.data]
    if not dry_run:
        [migrate_subscription_item(subscription_id, subscription_item)
         for subscription_item in subscription_items.data]


def do_work():
    n = Api(endpoint='http://localhost:8200', insecure=True)
    n.operation(n.get(n.current_session()),
                'switch-group',
                {'claim': 'group/nuvla-admin'})
    customers = n.search('customer',
                         last=10000,
                         filter='subscription-id!=null').resources
    print_section(f'Found {len(customers)} customers with subscription')
    loop_on_customers(customers, print_nuvla_customer)
    loop_on_customers(customers[:1], migrate_subscription)
    print_section(f'Number of errors: {number_of_error}')


if __name__ == '__main__':
    do_work()
