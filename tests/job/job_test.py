import unittest
from unittest.mock import patch
from mock import Mock
from nuvla.api import NuvlaError

from nuvla.job_engine.job import job, UnexpectedJobRetrieveError, JobNotFoundError
import nuvla.job_engine.job.version as version
from nuvla.api.models import CimiResource


class JobTestCase(unittest.TestCase):
    @patch('nuvla.job_engine.job.job.Version')
    @patch('nuvla.job_engine.job.Job.update_job')
    @patch('nuvla.job_engine.job.Job.get_cimi_job', return_value=CimiResource({}))
    def test_raise_JobVersionIsNoMoreSupported(self, _mock_get_cimi_job, _mock_update_job, mock_version):
        mock_version.engine_version = '4.5.2'
        mock_version.job_version_check.side_effect=version.JobVersionIsNoMoreSupported
        with self.assertRaises(version.JobVersionIsNoMoreSupported):
            job.Job('foo', None)
        job.Job.update_job.assert_called_once_with(
            state='FAILED',
            status_message='Job v0 is not supported by Job engine v4.5.2')

    @patch.object(version.Version, 'job_version_check', side_effect=version.JobVersionNotYetSupported)
    @patch('nuvla.job_engine.job.Job.update_job')
    @patch('nuvla.job_engine.job.Job.get_cimi_job', return_value=CimiResource({}))
    def test_raise_JobVersionNotYetSupported(self, _mock_get_cimi_job, mock_update_job, _mock_job_version_check):
        with self.assertRaises(version.JobVersionNotYetSupported):
            job.Job('foo', None)
        mock_update_job.assert_not_called()

    def test_raise_UnexpectedJobRetrieveError(self):
        with self.assertRaises(UnexpectedJobRetrieveError):
            job.Job('foo', None)

    def test_get_cimi_job_raise_UnexpectedJobRetrieveError(self):
        api = Mock()
        api.get.side_effect=NuvlaError
        with self.assertRaises(UnexpectedJobRetrieveError):
            job.Job('foo', api)

    @patch('time.sleep')
    def test_get_cimi_job_raise_JobNotFoundError(self, _mock):
        mock_api = Mock()
        response =  Mock()
        response.status_code = 404
        error = NuvlaError('Simulate not found', response)
        mock_api.get.side_effect=error
        with self.assertRaises(JobNotFoundError):
            job.Job('foo', mock_api)
        self.assertEqual(mock_api.get.call_count, 2)

    @patch.object(version.Version, 'job_version_check')
    @patch('time.sleep')
    def test_get_cimi_job_RetrySuccessfully(self, _mock_job_version_check, _mock_sleep):
        mock_api = Mock()
        response =  Mock()
        response.status_code = 404
        error = NuvlaError('Simulate not found', response)
        mock_api.get.side_effect=[error, CimiResource({})]
        job.Job('foo', mock_api)
        self.assertEqual(mock_api.get.call_count, 2)
