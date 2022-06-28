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


def loop_on_customers(customers, fn):
    for customer in customers:
        fn(customer)


def migrate_coupon(customer):
    try:
        customer_id = customer.data['customer-id']
        print_section(f"Customer {customer_id}")
        subscription_id = customer.data['subscription-id']
        s_customer = stripe.Customer.retrieve(customer_id)
        if s_customer.discount and s_customer.discount.coupon.valid:
            coupon_id = s_customer.discount.coupon.id
            coupon_name = s_customer.discount.coupon.name
            print_subsection(
                f'Customer {customer_id} is using coupon named "{coupon_name}"'
                f', id={coupon_id}')
            if not dry_run:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    coupon=coupon_id,
                    proration_behavior='none')
                print_subsection(
                    f'Coupon has been moved to subscription: '
                    f'{subscription.discount.coupon.id == coupon_id}')
                print_subsection(f'Deleting discount from customer.')
                stripe.Customer.delete_discount(s_customer)
        else:
            print("No coupon found!")
    except Exception as ex:
        print("ERROR: " + repr(ex))


def do_work():
    customers = n.search('customer',
                         last=10000,
                         filter='subscription-id!=null').resources
    customers_count = len(customers)
    print_section(f'Found {customers_count} customers')
    loop_on_customers(customers, migrate_coupon)


if __name__ == '__main__':
    do_work()
