import unittest
from mock import Mock
from unittest.mock import patch

from nuvla.job import job
from nuvla.api.models import CimiResource


class TestJob(unittest.TestCase):

    def test_job_version(self):
        queue = Mock()
        queue.get = Mock(return_value=b'foo')

        # No job version provided with the job. It will be set to the min value.
        # The job will be processed until engine's version is below 2.0.0.
        for ev in ['0.0.1', '1.0.0', '1.2.3']:
            job.engine_version = ev
            job.Job.get_cimi_job = Mock(return_value=CimiResource({}))
            job.Job.update_job = Mock()
            jb = job.Job(None, queue)
            assert jb.nothing_to_do is False

        # No job version provided with the job. It will be set to the min value.
        # The job will not be processed and removed from the queue.
        job.engine_version = '2.0.0'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({}))
        job.Job.update_job = Mock()
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "consume")
        jb.update_job.assert_called_once()
        assert jb.nothing_to_do is True

        # Job version is strictly smaller than M-1 of job engine version.
        # The job will not be processed and removed from the queue.
        job.engine_version = '3.2.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1.2.3'}))
        job.Job.update_job = Mock()
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "consume")
        jb.update_job.assert_called_once()
        assert jb.nothing_to_do is True

        # The job version might only indicate the major number.
        # Job version is strictly smaller than M-1 of job engine version.
        job.engine_version = '3.2.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1'}))
        job.Job.update_job = Mock()
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        jb.update_job.assert_called_once()
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "consume")
        assert jb.nothing_to_do is True

        # The job version might only indicate the major number.
        # Versions are equal. Job will be processed.
        job.engine_version = '1.0.0'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1'}))
        job.Job.update_job = Mock()
        jb = job.Job(None, queue)
        assert jb.nothing_to_do is False

        # Job and engine versions are equal.
        # Job will be processed.
        for v in ['0.0.1', '1.0.0', '7.6.5']:
            job.engine_version = v
            job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': v}))
            job.Job.update_job = Mock()
            job.retry_kazoo_queue_op = Mock()
            jb = job.Job(None, queue)
            jb.update_job.assert_not_called()
            job.retry_kazoo_queue_op.assert_not_called()
            assert jb.nothing_to_do is False

        # Job's version is higher that engine's.
        # Job is put back to the queue.
        job.engine_version = '0.0.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '0.0.2'}))
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "release")
        assert jb.nothing_to_do is True

        job.engine_version = '0.0.1.dev'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '0.0.2'}))
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "release")
        assert jb.nothing_to_do is True

        job.engine_version = '7.6.5'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '8.0.1'}))
        job.retry_kazoo_queue_op = Mock()
        jb = job.Job(None, queue)
        job.retry_kazoo_queue_op.assert_called_once_with(queue, "release")
        assert jb.nothing_to_do is True

    @patch.object(job.Job, 'get_cimi_job',
                  side_effect=[CimiResource({'action': 'start'}),
                               CimiResource({'action': 'bulk_start_deployment'})])
    @patch.object(job.Job, '_job_version_check')
    def test_is_bulk(self, _mock_job_version_check, _mock_get_cimi_job):
        queue = Mock()
        job.engine_version = '7.6.5'
        assert job.Job(None, queue).is_bulk is False
        assert job.Job(None, queue).is_bulk is True
