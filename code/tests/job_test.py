import unittest
from mock import Mock

from nuvla.job import job


class TestJob(unittest.TestCase):

    def test_job_version(self):
        queue = Mock()
        queue.get = Mock(return_value=b'foo')

        job.engine_version = '0.0.1'
        job.Job.get_cimi_job = Mock(return_value={'version': '0.0.1'})
        jb = job.Job(None, queue)
        assert jb.nothing_to_do == False

        job.engine_version = '0.0.1'
        job.Job.get_cimi_job = Mock(return_value={'version': '0.0.2'})
        jb = job.Job(None, queue)
        assert jb.nothing_to_do

        job.engine_version = '0.0.1-SNAPSHOT'
        job.Job.get_cimi_job = Mock(return_value={'version': '0.0.2'})
        jb = job.Job(None, queue)
        assert jb.nothing_to_do
