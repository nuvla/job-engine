import unittest
from datetime import datetime
from unittest.mock import  patch

from mock import Mock

from nuvla.job_engine.connector.nuvlaedge_k8s import NuvlaEdgeMgmtK8s

def get_item(*args):
    return {
        "href": "nuvlaedge/id-1234",
    }

class TestNuvlaEdgeK8s(unittest.TestCase):
    @patch('nuvla.job_engine.connector.nuvlaedge_k8s.Kubernetes.from_path_to_k8s_creds')
    def setUp(self, mock_from_path_to_k8s_creds):
        mock_job = Mock()
        mock_job.is_in_pull_mode = True
        mock_job.api = Mock()

        # Use PropertyMock to mock the __getitem__ method
        mock_job.__getitem__ = get_item

        self.k8s = NuvlaEdgeMgmtK8s(job=mock_job)

    def test_get_env_by_pattern(self):
        envs = [
            "NUVLAEDGE_UUID=nuvlaedge/id-1234",
            "NUVLAEDGE_VERSION=1.0.0",
            "NOT_A_MATCH.FAIL=1.0.0"]
        expected = [
            "--set", "NUVLAEDGE_UUID=nuvlaedge/id-1234",
            "--set", "NUVLAEDGE_VERSION=1.0.0"]
        pattern = r'\w+=.*$'

        result = self.k8s._get_env_by_pattern(envs, pattern)
        self.assertEqual(result, expected)

    def test_conf_to_vars(self):
        envs = [
            "nuvlaedge.image.tag=1.0.0",
            "nuvlaedge.image.organization=nuvladev",
            "NOT_A_MATCH/FAIL=1.0.0",
            "NOT_A_MATCH=1.0.0"]
        expected = [
            "--set", "nuvlaedge.image.tag=1.0.0",
            "--set", "nuvlaedge.image.organization=nuvladev"]
        result = self.k8s._conf_to_vars(envs)
        self.assertEqual(expected, result)

    def test_env_to_vars(self):
        envs = [
            "NUVLAEDGE_UUID=nuvlaedge/id-1234",
            "NUVLAEDGE_VERSION=1.0.0",
            "NOT_A_MATCH.FAIL=1.0.0",
            "nuvlaedge.image.organization=nuvladev"]
        expected = [
            "--set", "NUVLAEDGE_UUID=nuvlaedge/id-1234",
            "--set", "NUVLAEDGE_VERSION=1.0.0"]
        result = self.k8s._env_to_vars(envs)
        self.assertEqual(expected, result)

