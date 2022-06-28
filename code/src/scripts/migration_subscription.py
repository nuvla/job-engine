#!/usr/bin/env python
# -*- coding: utf-8 -*-

import stripe
from nuvla.api import Api

dry_run = False
stripe.api_key = "sk_test_"
n = Api(endpoint='http://localhost:8200', insecure=True)
n.login_password('', '')
n.operation(n.get(n.current_session()),
            'switch-group',
            {'claim': 'group/nuvla-admin'})

product_to_delete = ['prod_HYV40L9kxhkxjF', 'prod_HYV8zAoAKMsp5q',
                     'prod_HYVgsIbwoFh8hi']
product_to_replace = ['prod_HYVCzR5PYSPFLO']
price_nuvla_edge = 'price_1LAYnzHG9PNMTNBOTrWO9dZg'
product_nuvla_edge = 'prod_LsJQD6tPSY5Ik7'

number_preflight_error = 0
number_migration_error = 0


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
    if product_id not in \
            product_to_replace + product_to_delete + [product_nuvla_edge]:
        text += f"\n\t***ERROR*** This product is not expected!"
        global number_preflight_error
        number_preflight_error += number_preflight_error
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
            price=price_nuvla_edge,
            proration_behavior='none').id
        stripe.SubscriptionItem.create_usage_record(
            new_id,
            quantity=total_usage,
            action='set')
    if product_id in product_to_delete + product_to_replace:
        metered = subscription_item.price.recurring.usage_type == 'metered'
        stripe.SubscriptionItem.delete(subscription_item,
                                       proration_behavior='none',
                                       clear_usage=metered)


def already_migrated(subscription_items):
    return len(subscription_items) == 1 and \
           subscription_items[0].price.product == product_nuvla_edge


def migrate_subscription(customer):
    subscription_id = None
    try:
        subscription_id = customer.data['subscription-id']
        subscription_items = stripe.SubscriptionItem.list(
            subscription=customer.data['subscription-id']).data
        if already_migrated(subscription_items):
            print_section(f'Subscription {subscription_id} already migrated')
        else:
            print_section(f'Migrate subscription {subscription_id}')
            [print_subscription_item(subscription_item)
             for subscription_item in subscription_items]
            if not dry_run:
                [migrate_subscription_item(subscription_id, subscription_item)
                 for subscription_item in subscription_items]
    except Exception as ex:
        global number_migration_error
        number_migration_error += 1
        print_subsection(
            f"Subscription {subscription_id} migration failed!" + repr(ex))


def do_migrations(customers):
    customers_count = len(customers)
    print_section("Starting Migration")
    loop_on_customers(customers, migrate_subscription)
    migrated_success = customers_count - number_migration_error
    migrated_text = f"\nMigrated {migrated_success}/{customers_count}"
    if number_migration_error == 0:
        print_section(f"Migration of customers done successfully."
                      + migrated_text)
    else:
        print_section(
            f'Migration of customers got issues! '
            f'\nNumber of errors: {number_migration_error}'
            + migrated_text)


def do_work():
    customers = n.search('customer',
                         last=10000,
                         filter='subscription-id!=null').resources
    customers_count = len(customers)
    print_section(f'Found {customers_count} customers with subscription')
    loop_on_customers(customers, print_nuvla_customer)
    print_section(f'Number of preflight errors: {number_preflight_error}')
    if dry_run:
        print_subsection("Dry run is on")
        do_migrations(customers)
    else:
        if number_preflight_error == 0:
            do_migrations(customers)
        else:
            print_section('Preflight errors this script is stopped here.')
            exit(-1)


if __name__ == '__main__':
    do_work()
