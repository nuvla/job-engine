#!/usr/bin/env python

import unittest
from unittest.mock import MagicMock, patch

from nuvla.job.distribution import DistributionBase
from nuvla.job.distributions.trial_end import \
    TrialEndJobsDistribution, \
    build_filter_customers, \
    list_subscription_ids


class TestTrialEndJobsDistribution(unittest.TestCase):

    def setUp(self):
        self.patcher = patch.object(DistributionBase, '_start_distribution')
        self.mock_object = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_list_subscription_ids(self):
        trials = []
        self.assertListEqual([], list_subscription_ids(trials))
        trials = [{'id': '1'}]
        self.assertListEqual(['1'], list_subscription_ids(trials))
        trials = [{'id': '1'}, {'id': '2'}]
        self.assertListEqual(['1', '2'], list_subscription_ids(trials))
        trials = [{'id': '1'}, {'id': '2'}, {}]
        self.assertListEqual(['1', '2'], list_subscription_ids(trials), "should not fail even if trials is missing ids")

    def test_build_filter_customers(self):
        subscription_ids = []
        self.assertEqual('', build_filter_customers(subscription_ids))
        subscription_ids = ['1']
        self.assertEqual('subscription-id="1"', build_filter_customers(subscription_ids))
        subscription_ids = ['1', '2']
        self.assertEqual('subscription-id="1" or subscription-id="2"', build_filter_customers(subscription_ids))
        subscription_ids = ['1', '2', '3']
        self.assertEqual('subscription-id="1" or subscription-id="2" or subscription-id="3"',
                         build_filter_customers(subscription_ids))

    @patch.object(TrialEndJobsDistribution, 'search_customers')
    @patch('nuvla.job.distributions.trial_end.build_filter_customers')
    def test_trialing_customers(self,
                                mock_build_filter_customers,
                                mock_search_customers):
        self.obj = TrialEndJobsDistribution(MagicMock())
        trial_1 = {'id': '1'}
        trial_2 = {'id': '2'}
        customer_1_id = 'customer/1'
        customer_2_id = 'customer/2'
        customer_1 = {'id': customer_1_id}
        customer_2 = {'id': customer_2_id}

        mock_build_filter_customers.return_value = ''
        trials = [trial_2]
        self.assertListEqual([], self.obj.get_customers_ids(trials), 'search customers without filter is not executed')

        mock_build_filter_customers.return_value = 'subscription-id="2"'
        mock_search_customers.return_value = [customer_2]
        self.assertListEqual([customer_2_id], self.obj.get_customers_ids(trials))

        trials = [trial_1, trial_2]
        mock_search_customers.return_value = [customer_1, customer_2]
        self.assertListEqual([customer_1_id, customer_2_id], self.obj.get_customers_ids(trials))
