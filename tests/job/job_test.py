import unittest
from mock import Mock

from nuvla.job_engine.job import job
from nuvla.api.models import CimiResource


class TestJob(unittest.TestCase):

    def test_no_job_version_provided(self):
        # No job version provided with the job. It will be set to the min value.
        # The job will be processed until engine's version is below 2.0.0.
        for ev in ['0.0.1', '1.0.0', '1.2.3']:
            job.engine_version = ev
            job.Job.get_cimi_job = Mock(return_value=CimiResource({}))
            job.Job('foo', None)

    def test_no_job_version_provided_engine_2_0_0(self):
        # No job version provided with the job. It will be set to the min value.
        job.engine_version = '2.0.0'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({}))
        job.Job.update_job = Mock()
        with self.assertRaises(job.JobVersionIsNoMoreSupported):
            job.Job('foo', None)

    def test_job_version_provided_engine_3_2_1(self):
        # Job version is strictly smaller than M-1 of job engine version.
        # The job will not be processed and removed from the queue.
        job.engine_version = '3.2.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1.2.3'}))
        job.Job.update_job = Mock()
        with self.assertRaises(job.JobVersionIsNoMoreSupported):
            job.Job('foo', None)

    def test_job_version_provided_major_only_engine_3_2_1(self):
        # Job version is strictly smaller than M-1 of job engine version.
        # The job will not be processed and removed from the queue.
        job.engine_version = '3.2.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1'}))
        job.Job.update_job = Mock()
        with self.assertRaises(job.JobVersionIsNoMoreSupported):
            job.Job('foo', None)

    def test_job_version_provided_major_only_engine_1_0_0(self):
        # Job version is strictly smaller than M-1 of job engine version.
        # Versions are equal. Job will be processed.
        job.engine_version = '1.0.0'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '1'}))
        job.Job.update_job = Mock()
        job.Job('foo', None)

    def test_job_version_engine_version_are_equal(self):
        # Job and engine versions are equal.
        # Job will be processed.
        for v in ['0.0.1', '1.0.0', '7.6.5']:
            job.engine_version = v
            job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': v}))
            job.Job.update_job = Mock()
            job.Job('foo', None)

    def test_job_version_is_higher_than_engine_version(self):
        # Job's version is higher that engine's.
        job.engine_version = '0.0.1'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '0.0.2'}))
        with self.assertRaises(job.JobVersionBiggerThanEngine):
            job.Job('foo', None)

    def test_job_version_is_higher_than_engine_version_dev(self):
        # Job's version is higher that engine's.
        job.engine_version = '0.0.1.dev'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '0.0.2'}))
        with self.assertRaises(job.JobVersionBiggerThanEngine):
            job.Job('foo', None)


    def test_job_version_is_higher_than_engine_version_7_6_5(self):
        job.engine_version = '7.6.5'
        job.Job.get_cimi_job = Mock(return_value=CimiResource({'version': '8.0.1'}))
        with self.assertRaises(job.JobVersionBiggerThanEngine):
            job.Job('foo', None)
