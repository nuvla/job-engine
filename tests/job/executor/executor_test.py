import sys
import unittest
from unittest.mock import MagicMock, patch, Mock, call
import nuvla.api
from nuvla.job_engine.job.executor.executor import Executor, LocalOneJobQueue
from nuvla.job_engine.job.base import Base
from nuvla.job_engine.job.job import Job


class TestExecutor(unittest.TestCase):
    def setUp(self):
        patcher_base = patch.object(Base, '__init__', return_value=None)
        patcher_base.start()
        self.executor = Executor()
        self.executor.api = MagicMock(spec=nuvla.api.Api)
        self.executor.api.session = MagicMock()
        self.executor.args = MagicMock(autospec=True)
        self.executor.name = 'foo'
        self.addCleanup(patcher_base.stop)

    @patch.object(sys, 'exit')
    def test_process_jobs_local_one_job(self, mock_sys):
        self.executor._process_jobs(LocalOneJobQueue('foo'))
        mock_sys.assert_called_once_with(0)

    @patch.object(sys, 'exit')
    @patch.object(Executor, 'stop_event')
    @patch.object(Executor, 'get_action_instance')
    @patch.object(Executor, 'process_job')
    @patch('nuvla.job_engine.job.executor.executor.Job')
    def test_process_jobs_until_stop_event_set(self,
                                               mock_job,
                                               mock_process_job,
                                               mock_get_action_instance,
                                               mock_stop_event,
                                               mock_sys):
        job_1 = Mock()
        job_1.id = 'job-1'
        job_1.nothing_to_do = False
        job_2 = Mock()
        job_2.id = 'job-2'
        job_2.nothing_to_do = False
        mock_job.side_effect = [job_1, job_2]
        mock_get_action_instance.return_value.do_work.return_value = 0
        mock_stop_event.is_set.side_effect = [False, False, True]
        self.executor._process_jobs(MagicMock())
        self.assertEqual(mock_stop_event.is_set.call_count, 3)
        self.assertEqual(mock_process_job.call_count, 2)
        mock_process_job.assert_has_calls([call(job_1), call(job_2)])
        mock_sys.assert_called_once_with(0)

    @patch.object(sys, 'exit')
    @patch.object(Executor, 'stop_event')
    @patch.object(Executor, 'get_action_instance')
    @patch.object(Executor, 'process_job')
    @patch('nuvla.job_engine.job.executor.executor.Job')
    def test_process_jobs_nothing_to_do(self,
                                               mock_job,
                                               mock_process_job,
                                               mock_get_action_instance,
                                               mock_stop_event,
                                               mock_sys):
        job_1 = Mock()
        job_1.id = 'job-1'
        job_1.nothing_to_do = True
        mock_job.return_value = job_1
        mock_get_action_instance.return_value.do_work.return_value = 0
        mock_stop_event.is_set.side_effect = [False, True]
        self.executor._process_jobs(MagicMock())
        self.assertFalse(mock_process_job.called)
        mock_sys.assert_called_once_with(0)
