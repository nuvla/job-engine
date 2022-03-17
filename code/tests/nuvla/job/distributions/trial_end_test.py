#!/usr/bin/env python

import unittest
from unittest.mock import MagicMock, patch

from nuvla.job.distribution import DistributionBase
from nuvla.job.distributions.trial_end import \
    TrialEndJobsDistribution, \
    build_filter_customers


class TestTrialEndJobsDistribution(unittest.TestCase):

    def setUp(self):
        self.patcher = patch.object(DistributionBase, '_start_distribution')
        self.mock_object = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_is_ignored_customer(self):
        obj = TrialEndJobsDistribution(MagicMock())
        obj._ignored_customers_ids = ['cus_1']
        self.assertTrue(obj.is_ignored_customer('cus_1'))
        obj._ignored_customers_ids = []
        self.assertFalse(obj.is_ignored_customer('cus_1'))
        obj._ignored_customers_ids = ['cus_1', 'cus_2', 'cus_3']
        self.assertTrue(obj.is_ignored_customer('cus_2'))
        self.assertTrue(obj.is_ignored_customer('cus_3'))

    def test_list_subscription_ids(self):
        obj = TrialEndJobsDistribution(MagicMock())
        obj._trials = []
        trial_1 = {'id': 'sub_1',
                   'customer': 'cus_1'}
        trial_2 = {'id': 'sub_2',
                   'customer': 'cus_2'}
        self.assertListEqual(
            [], obj.list_subscription_ids())
        obj._trials = [trial_1]
        self.assertListEqual(
            ['sub_1'], obj.list_subscription_ids())
        obj._trials = [trial_1, trial_2]
        self.assertListEqual(
            ['sub_1', 'sub_2'], obj.list_subscription_ids())
        obj._trials = [trial_1, trial_2, {}]
        self.assertListEqual(
            ['sub_1', 'sub_2'], obj.list_subscription_ids(),
            'should not fail even if trials is missing ids')
        obj._ignored_customers_ids = ['cus_1']
        self.assertListEqual(['sub_2'], obj.list_subscription_ids())

    def test_build_filter_customers(self):
        subscription_ids = []
        self.assertEqual('', build_filter_customers(subscription_ids))
        subscription_ids = ['1']
        self.assertEqual('subscription-id="1"',
                         build_filter_customers(subscription_ids))
        subscription_ids = ['1', '2']
        self.assertEqual('subscription-id="1" or subscription-id="2"',
                         build_filter_customers(subscription_ids))
        subscription_ids = ['1', '2', '3']
        self.assertEqual(
            'subscription-id="1" or subscription-id="2" or subscription-id="3"',
            build_filter_customers(subscription_ids))

    @patch.object(TrialEndJobsDistribution, 'search_customers')
    @patch('nuvla.job.distributions.trial_end.build_filter_customers')
    def test_get_customers(self,
                           mock_build_filter_customers,
                           mock_search_customers):
        obj = TrialEndJobsDistribution(MagicMock())
        trial_1 = {'id': '1'}
        trial_2 = {'id': '2'}
        customer_1 = {'id': 'customer/1'}
        customer_2 = {'id': 'customer/2'}

        mock_build_filter_customers.return_value = ''
        obj._trials = [trial_2]
        self.assertListEqual([], obj.get_customers(),
                             'search customers without filter is not executed')

        mock_build_filter_customers.return_value = 'subscription-id="2"'
        mock_search_customers.return_value = [customer_2]
        self.assertListEqual([customer_2], obj.get_customers())

        obj._trials = [trial_1, trial_2]
        mock_search_customers.return_value = [customer_1, customer_2]
        self.assertListEqual([customer_1, customer_2],
                             obj.get_customers())
