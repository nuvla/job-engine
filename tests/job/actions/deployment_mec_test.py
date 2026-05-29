import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from nuvla.job_engine.job.actions.deployment_state import DeploymentStateJob
from nuvla.job_engine.job.actions.deployment_start import DeploymentStartJob
from nuvla.job_engine.job.actions.deployment_stop import DeploymentStopJob
from nuvla.job_engine.job.actions.utils.mm3_client import Mm3ClientError


class TestDeploymentMecFlow(unittest.TestCase):
    def test_deployment_state_skips_generic_polling_for_mec_deployments(self):
        obj = DeploymentStateJob.__new__(DeploymentStateJob)
        obj.job = MagicMock()
        obj.deployment = SimpleNamespace(data={'module': {'subtype': 'application_mec'}})
        obj.create_update_hostname_output_parameter = MagicMock()
        obj.create_update_ips_output_parameters = MagicMock()
        obj.application_params_update = MagicMock()

        obj.get_application_state()

        obj.job.set_status_message.assert_called_once_with('Skipping generic deployment_state for MEC deployment')
        obj.create_update_hostname_output_parameter.assert_not_called()
        obj.create_update_ips_output_parameters.assert_not_called()
        obj.application_params_update.assert_not_called()

    def test_deployment_state_detects_mec_subtype(self):
        obj = DeploymentStateJob.__new__(DeploymentStateJob)
        obj.deployment = SimpleNamespace(data={'module': {'subtype': 'application_mec'}})

        self.assertTrue(obj.is_mec_deployment())

    def test_handle_deployment_skips_generic_output_params_for_mec_jobs(self):
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.is_mec_job = MagicMock(return_value=True)
        obj.create_user_output_params = MagicMock()
        obj.action_on_application = MagicMock()

        obj.handle_deployment()

        obj.create_user_output_params.assert_not_called()
        obj.action_on_application.assert_called_once_with()

    def test_handle_deployment_keeps_generic_output_params_for_non_mec_jobs(self):
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.is_mec_job = MagicMock(return_value=False)
        obj.create_user_output_params = MagicMock()
        obj.action_on_application = MagicMock()

        obj.handle_deployment()

        obj.create_user_output_params.assert_called_once_with()
        obj.action_on_application.assert_called_once_with()

    def test_start_action_uses_mec_branch(self):
        job = MagicMock()
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = job
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='INSTANTIATE')
        obj.instantiate_mec_application = MagicMock()

        obj.action_on_application()

        obj.instantiate_mec_application.assert_called_once_with()
        job.set_progress.assert_called_once_with(90)

    def test_instantiate_mec_application_persists_southbound_id(self):
        job = MagicMock()
        job.get.side_effect = lambda key, default=None: {
            'mec-host-id': 'nuvlabox/edge-1',
            'mec-request-params': {'grantId': 'grant-123'}
        }.get(key, default)

        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = job
        obj.deployment_id = 'deployment/test-1'
        obj.deployment = SimpleNamespace(data={'module': {'href': 'module/app-1'}})
        obj.api = SimpleNamespace(session=SimpleNamespace(verify=True))
        obj.set_mec_app_instance_id = MagicMock()
        obj.set_mec_operation_id = MagicMock()
        obj.mepm_endpoint = MagicMock(return_value='https://mepm.example.com')
        mm3_client = MagicMock()
        mm3_client.create_app_instance.return_value = {'id': 'southbound-app-1',
                                                       'operationId': 'southbound-op-1'}
        obj.mm3_client = MagicMock(return_value=mm3_client)

        obj.instantiate_mec_application()

        mm3_client.create_app_instance.assert_called_once()
        obj.set_mec_app_instance_id.assert_called_once_with('southbound-app-1')
        obj.set_mec_operation_id.assert_called_once_with('southbound-op-1')
        job._edit_job_multi.assert_called_once_with({'mec-southbound-operation-id': 'southbound-op-1'})
        job.set_status_message.assert_called_once()

    def test_stop_action_uses_mec_terminate_branch(self):
        job = MagicMock()
        obj = DeploymentStopJob.__new__(DeploymentStopJob)
        obj.job = job
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='TERMINATE')
        obj.get_mec_app_instance_id = MagicMock(return_value='southbound-app-1')
        obj.set_mec_operation_id = MagicMock()
        obj.mepm_endpoint = MagicMock(return_value='https://mepm.example.com')
        mm3_client = MagicMock()
        mm3_client.delete_app_instance.return_value = {}
        obj.mm3_client = MagicMock(return_value=mm3_client)

        obj.stop_application()

        mm3_client.delete_app_instance.assert_called_once_with('southbound-app-1')
        obj.set_mec_operation_id.assert_not_called()
        job._edit_job_multi.assert_not_called()
        job.set_status_message.assert_called_once()

    def test_stop_action_fails_without_persisted_mec_id(self):
        obj = DeploymentStopJob.__new__(DeploymentStopJob)
        obj.job = MagicMock()
        obj.deployment_id = 'deployment/test-1'
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='TERMINATE')
        obj.get_mec_app_instance_id = MagicMock(return_value=None)

        with self.assertRaises(Mm3ClientError):
            obj.stop_application()

    def test_start_action_uses_mec_operate_branch(self):
        job = MagicMock()
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = job
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='OPERATE')
        obj.operate_mec_application = MagicMock()

        obj.action_on_application()

        obj.operate_mec_application.assert_called_once_with()
        job.set_progress.assert_called_once_with(90)

    def test_operate_mec_application_persists_southbound_operation_id(self):
        job = MagicMock()
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = job
        obj.deployment_id = 'deployment/test-1'
        obj.get_mec_app_instance_id = MagicMock(return_value='southbound-app-1')
        obj.get_mec_change_state_to = MagicMock(return_value='STARTED')
        obj.set_mec_operation_id = MagicMock()
        obj.mepm_endpoint = MagicMock(return_value='https://mepm.example.com')
        mm3_client = MagicMock()
        mm3_client.operate_app_instance.return_value = {'operationId': 'southbound-op-3'}
        obj.mm3_client = MagicMock(return_value=mm3_client)

        obj.operate_mec_application()

        mm3_client.operate_app_instance.assert_called_once_with('southbound-app-1', 'STARTED')
        obj.set_mec_operation_id.assert_called_once_with('southbound-op-3')
        job._edit_job_multi.assert_called_once_with({'mec-southbound-operation-id': 'southbound-op-3'})
        job.set_status_message.assert_called_once()

    def test_stop_action_uses_mec_operate_branch(self):
        job = MagicMock()
        obj = DeploymentStopJob.__new__(DeploymentStopJob)
        obj.job = job
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='OPERATE')
        obj.get_mec_app_instance_id = MagicMock(return_value='southbound-app-1')
        obj.get_mec_change_state_to = MagicMock(return_value='STOPPED')
        obj.set_mec_operation_id = MagicMock()
        obj.mepm_endpoint = MagicMock(return_value='https://mepm.example.com')
        mm3_client = MagicMock()
        mm3_client.operate_app_instance.return_value = {'operationId': 'southbound-op-2'}
        obj.mm3_client = MagicMock(return_value=mm3_client)

        obj.stop_application()

        mm3_client.operate_app_instance.assert_called_once_with('southbound-app-1', 'STOPPED')
        obj.set_mec_operation_id.assert_called_once_with('southbound-op-2')
        job._edit_job_multi.assert_called_once_with({'mec-southbound-operation-id': 'southbound-op-2'})
        job.set_status_message.assert_called_once()

    def test_terminate_normalizes_deployment_to_created(self):
        obj = DeploymentStopJob.__new__(DeploymentStopJob)
        obj.job = MagicMock()
        obj.deployment_id = 'deployment/test-1'
        obj.log = MagicMock()
        obj.try_handle_raise_exception = MagicMock()
        obj.try_delete_deployment_credentials = MagicMock()
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='TERMINATE')
        obj.api_dpl = SimpleNamespace(nuvla=MagicMock())

        rc = obj.stop_deployment()

        self.assertEqual(0, rc)
        obj.api_dpl.nuvla.edit.assert_not_called()
        obj.try_delete_deployment_credentials.assert_not_called()

    def test_operate_stop_preserves_deployment_credentials(self):
        obj = DeploymentStopJob.__new__(DeploymentStopJob)
        obj.job = MagicMock()
        obj.deployment_id = 'deployment/test-1'
        obj.log = MagicMock()
        obj.try_handle_raise_exception = MagicMock()
        obj.try_delete_deployment_credentials = MagicMock()
        obj.is_mec_job = MagicMock(return_value=True)
        obj.mec_operation_type = MagicMock(return_value='OPERATE')
        obj.api_dpl = MagicMock()

        rc = obj.stop_deployment()

        self.assertEqual(0, rc)
        obj.try_delete_deployment_credentials.assert_not_called()
        obj.api_dpl.set_state_stopped.assert_not_called()

    def test_start_deployment_does_not_finalize_mec_state(self):
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = MagicMock()
        obj.deployment_id = 'deployment/test-1'
        obj.log = MagicMock()
        obj.try_handle_raise_exception = MagicMock()
        obj.is_mec_job = MagicMock(return_value=True)
        obj.api_dpl = MagicMock()

        rc = obj.action_on_deployment()

        self.assertEqual(0, rc)
        obj.api_dpl.set_state_started.assert_not_called()

    def test_start_deployment_keeps_non_mec_state_transition(self):
        obj = DeploymentStartJob.__new__(DeploymentStartJob)
        obj.job = MagicMock()
        obj.deployment_id = 'deployment/test-1'
        obj.log = MagicMock()
        obj.try_handle_raise_exception = MagicMock()
        obj.is_mec_job = MagicMock(return_value=False)
        obj.api_dpl = MagicMock()

        rc = obj.action_on_deployment()

        self.assertEqual(0, rc)
        obj.api_dpl.set_state_started.assert_called_once_with('deployment/test-1')
