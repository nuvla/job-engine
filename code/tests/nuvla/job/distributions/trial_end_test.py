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

    @patch.object(TrialEndJobsDistribution, 'get_trials')
    def test_list_customer_ids(self, mock_get_trials):
        obj = TrialEndJobsDistribution(MagicMock())
        mock_get_trials.return_value = []
        trial_1 = {'id': 'sub_1',
                   'customer': 'cus_1'}
        trial_2 = {'id': 'sub_2',
                   'customer': 'cus_2'}
        self.assertListEqual(
            [], obj.list_customer_ids())
        mock_get_trials.return_value = [trial_1]
        self.assertListEqual(
            ['cus_1'], obj.list_customer_ids())
        mock_get_trials.return_value = [trial_1, trial_2]
        self.assertListEqual(
            ['cus_1', 'cus_2'], obj.list_customer_ids())
        mock_get_trials.return_value = [trial_1, trial_2, {}]
        self.assertListEqual(
            ['cus_1', 'cus_2'], obj.list_customer_ids(),
            'should not fail even if trials is missing ids')

    def test_build_filter_customers(self):
        self.assertEqual(
            '(customer-id="1" or customer-id="2" or customer-id="3")',
            build_filter_customers(['1', '2', '3']))

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
