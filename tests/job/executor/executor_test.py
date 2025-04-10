import sys
import unittest
from unittest.mock import MagicMock, patch, Mock
from nuvla.job_engine.job.executor.executor import Executor, LocalOneJobQueue
from nuvla.job_engine.job.base import Base
from nuvla.job_engine.job.job import Job, JobNotFoundError
from nuvla.job_engine.job.actions import ActionNotImplemented
from nuvla.api import NuvlaError

job_id = 'job/1'


class MockJob(dict):
    def __init__(self, id):
        super().__init__(action='action-that-not-exist')
        self.id = id

    update_job = MagicMock()


class ExecutorTestCase(unittest.TestCase):
    @patch.object(Base, '__init__')
    def setUp(self, mock_base):
        Executor.api = MagicMock()
        Executor.args = MagicMock()
        Executor.name = 'foo'
        self.executor = Executor()
        self.executor.queue = MagicMock()
        self.executor.queue.get.return_value.decode.return_value = job_id
        self.executor.queue.processing_element = job_id

    @patch.object(sys, 'exit')
    @patch.object(Executor, 'get_action_instance')
    def test_process_jobs_local_one_job(self,
                                        mock_get_action_instance,
                                        mock_sys):
        mock_get_action_instance.return_value.do_work.return_value = 0
        self.executor.queue = LocalOneJobQueue('foo')
        self.executor._process_jobs()
        mock_sys.assert_called_once_with(0)

    @patch.object(sys, 'exit')
    @patch.object(Executor, 'stop_event')
    @patch.object(Executor, '_process_job')
    def test_process_jobs_until_stop_event_set(self,
                                               mock_process_job,
                                               mock_stop_event,
                                               mock_sys):
        mock_stop_event.is_set.side_effect = [False, False, True]
        self.executor._process_jobs()
        self.assertEqual(mock_stop_event.is_set.call_count, 3)
        self.assertEqual(mock_process_job.call_count, 2)
        mock_sys.assert_called_once_with(0)

    @patch.object(Job, '__init__', side_effect=Exception('Simulate exception'))
    def test_process_job_unexpected_error(self, _mock_job):
        with self.assertLogs(level='DEBUG') as lc:
            self.executor._process_job()
            self.assertEqual(
                ['INFO:root:Got new job/1.',
                 "ERROR:root:Unexpected exception occurred during process of job/1: Exception('Simulate exception')",
                 'INFO:root:Queue consume job/1.'],
                lc.output)
        self.executor.queue.consume.assert_called_once()

    @patch.object(Job, 'get_cimi_job', side_effect=Exception('Simulate exception'))
    def test_process_job_unexpected_job_retrieve_error(self, mock_get_cimi_job):
        with self.assertLogs(level='DEBUG') as lc:
            self.executor._process_job()
            self.assertEqual(
                ['INFO:root:Got new job/1.',
                 "ERROR:root:Fatal error when trying to retrieve job/1!: Exception('Simulate "
                 "exception')",
                 'INFO:root:Queue release job/1.'],
                lc.output)
        self.executor.queue.release.assert_called_once()

    @patch('time.sleep')
    def test_process_job_unexpected_job_not_found(self, _mock_time):
        response =  Mock()
        response.status_code = 404
        self.executor.api.get.side_effect = NuvlaError('', response)
        with self.assertLogs(level='DEBUG') as lc:
            self.executor._process_job()
            self.assertEqual(
                ['INFO:root:Got new job/1.',
                 'WARNING:job:Retrieve of job/1 failed. Attempt: 0 Will retry in 2s.',
                 'WARNING:job:Retrieve of job/1 failed. Attempt: 1 Will retry in 2s.',
                 'ERROR:root:Retrieved job/1 not found! Message: ',
                 'INFO:root:Queue consume job/1.'],
                lc.output)
        self.executor.queue.consume.assert_called_once()

    @patch('nuvla.job_engine.job.executor.executor.Job')
    def test_process_job_action_not_implemented(self, mock_job):
        mock_job_instance = MockJob(job_id)
        mock_job.return_value = mock_job_instance
        with self.assertLogs(level='DEBUG') as lc:
            self.executor._process_job()
            self.assertEqual(['INFO:root:Got new job/1.',
                              'INFO:root:Process job/1 with action action-that-not-exist.',
                              'ERROR:root:Not implemented action job/1: action-that-not-exist',
                              'INFO:root:Queue consume job/1.'],
                             lc.output)
        mock_job_instance.update_job.assert_called_once_with(
            state='FAILED',
            status_message='Not implemented action job/1: action-that-not-exist')
        self.executor.queue.consume.assert_called_once()
