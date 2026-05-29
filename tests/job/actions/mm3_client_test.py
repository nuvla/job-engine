import unittest
from unittest.mock import MagicMock, patch

from nuvla.job_engine.job.actions.utils.mm3_client import Mm3Client


class TestMm3Client(unittest.TestCase):
    def _ok_response(self):
        response = MagicMock()
        response.status_code = 200
        response.content = b'{}'
        response.json.return_value = {}
        return response

    @patch('nuvla.job_engine.job.actions.utils.mm3_client.requests.request')
    def test_request_sends_job_engine_caller_header(self, mock_request):
        mock_request.return_value = self._ok_response()

        client = Mm3Client('http://mock-mepm.local')
        client.create_app_instance({'app-instance-id': 'deployment/test-1'})

        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        self.assertEqual('job-engine', kwargs['headers']['X-Nuvla-Mm3-Caller'])

    @patch('nuvla.job_engine.job.actions.utils.mm3_client.requests.request')
    def test_app_lifecycle_routes_use_canonical_mm3_path(self, mock_request):
        mock_request.return_value = self._ok_response()

        client = Mm3Client('http://mock-mepm.local')
        client.create_app_instance({'app-instance-id': 'deployment/test-1'})
        client.get_app_instance('southbound-app-1')
        client.delete_app_instance('southbound-app-1')
        client.operate_app_instance('southbound-app-1', 'STOPPED')

        self.assertEqual(
            [
                'http://mock-mepm.local/mm3/app_lcm/v1/app_instances',
                'http://mock-mepm.local/mm3/app_lcm/v1/app_instances/southbound-app-1',
                'http://mock-mepm.local/mm3/app_lcm/v1/app_instances/southbound-app-1',
                'http://mock-mepm.local/mm3/app_lcm/v1/app_instances/southbound-app-1/operate'
            ],
            [call.args[1] for call in mock_request.call_args_list]
        )
