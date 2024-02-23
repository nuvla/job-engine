#!/usr/bin/env python

import unittest
from unittest.mock import MagicMock, patch

from nuvla.job_engine.job.actions.deployment_log_fetch import DeploymentLogFetchJob


class TestResourceLogFetchJob(unittest.TestCase):
    def setUp(self) -> None:
        self.obj = DeploymentLogFetchJob(MagicMock(), MagicMock())

    @patch(
        'nuvla.job_engine.job.actions.utils.resource_log_fetch.build_update_resource_log')
    @patch.object(DeploymentLogFetchJob, 'get_components_logs')
    @patch.object(DeploymentLogFetchJob, 'update_resource_log')
    def test_fetch_log(self,
                       mock_update_resource_log,
                       mock_get_components_logs,
                       mock_build_update_resource_log):
        mock_build_update_resource_log.return_value = {}
        self.obj.resource_log_id = '1'
        self.obj.fetch_log()
        mock_get_components_logs.assert_called()
        mock_update_resource_log.assert_called_once_with('1', {})
