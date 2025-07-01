import sys
import time
import unittest
from unittest.mock import MagicMock, patch, Mock
from nuvla.job_engine.job.base import Base
from nuvla.job_engine.job.distributions import Distributions
from nuvla.job_engine.job.distributor.distributor import Distributor
from nuvla.job_engine.job.distributor import distributor

from nuvla.job_engine.job.distribution import DistributionBase

from nuvla.job_engine.job.util import override

class DummyTestActionsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'dummy_action'

    def __init__(self, distributor):
        super(DummyTestActionsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 15  # 15s
        self._start_distribution()

    def _start_distribution(self):
        self._job_distribution()

    @override
    def job_generator(self):
        raise Exception('failed')

class DistributorTestCase(unittest.TestCase):

    @patch.object(Base, '__init__')
    def setUp(self, mock_base):
        self.distributor = Distributor()
        self.distributor.name = 'toto'
        self.distributor.args = MagicMock()

    @patch.object(sys, 'exit')
    @patch.object(Base, 'stop_event')
    def test_distributor_should_shutdown_on_stop_event(self, mock_stop_event, mock_sys_exit):
        mock_stop_event.is_set.return_value = True
        self.distributor.do_work()
        mock_sys_exit.assert_called_once_with(0)

    @patch('nuvla.job_engine.job.distributor.distributor.distributions', {"a": None})
    @patch.object(sys, 'exit')
    @patch.object(Base, 'stop_event')
    def test_distributor_should_loop_until_stop_event_is_set(self, mock_stop_event, mock_sys_exit):
        self.distributor.check_and_recreate_thread_on_exception = Mock()
        mock_stop_event.is_set.side_effect = [False, False, False, True]
        self.distributor.do_work()
        self.assertEqual(self.distributor.check_and_recreate_thread_on_exception.call_count, 3)
        mock_sys_exit.assert_called_once_with(0)

    @patch('nuvla.job_engine.job.distributor.distributor.distributions', {"a": None})
    @patch('nuvla.job_engine.job.distributor.distributor.get_distribution')
    @patch.object(sys, 'exit')
    @patch.object(Base, 'stop_event')
    def test_distributor_distribution_thread_should_be_recreated_in_case_of_exception(
            self, mock_stop_event, mock_sys_exit, mock_get_distribution):
        mock_get_distribution.return_value = Mock(side_effect=[Exception(), 1])
        mock_stop_event.is_set.side_effect = [False, False, True]
        self.distributor.do_work()
        mock_get_distribution.assert_called_with("a")
        self.assertEqual(mock_get_distribution.call_count, 2)
        mock_sys_exit.assert_called_once_with(0)

    @patch('nuvla.job_engine.job.distributor.distributor.distributions', {"dummy_action": DummyTestActionsDistribution})
    @patch('nuvla.job_engine.job.distributor.distributor.get_distribution')
    @patch.object(sys, 'exit')
    @patch.object(Base, 'stop_event')
    def test_distributor_distribution_thread_should_be_recreated_in_case_of_exception_while_generating_job(
            self, mock_stop_event, mock_sys_exit, mock_get_distribution):

        mock_get_distribution.return_value = DummyTestActionsDistribution
        mock_stop_event.is_set.side_effect = [False, False, False, False, True, True]
        self.distributor.do_work()
        self.assertEqual(mock_get_distribution.call_count, 3)
        mock_sys_exit.assert_called_once_with(0)
