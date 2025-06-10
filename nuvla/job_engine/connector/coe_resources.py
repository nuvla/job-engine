import json
import re

import docker
import docker.errors

import logging
import traceback

log = logging.getLogger('coe_resources')

class MissingFieldException(Exception):
    def __init__(self, field):
        self.field = field
        super().__init__(f"Missing field: {field}")


class DockerCoeResources:
    def __init__(self, job):
        self.job = job
        self.docker_client = docker.from_env()

    def _unsupported_action_job_response(self, action: str):
        return self._new_job_response(False, 0, f"Unsupported action: {action}")

    def _unsupported_resource_for_action_job_response(self, resource: str, action: str):
        return self._new_job_response(False, 0, f"Unsupported resource {resource} for action {action}")

    @staticmethod
    def _new_job_response(success: bool, return_code: int, message: str):
        return {
            'success': success,
            'return-code': return_code,
            'message': message
        }

    def handle_resources(self, action_list: list[dict]) -> list[dict]:
        if self.docker_client is None:
            self.docker_client = docker.from_env()

        action_factory: dict[str, dict[str, callable]] = {
            "pull": {
                "image": self._pull_image
            },
            "remove": {
                "container": self._remove_container,
                "volume": self._remove_volume,
                "network": self._remove_network,
                "image": self._remove_image
            }
        }

        return [self._handle_resource(resource_action, action_factory) for resource_action in action_list]

    def _handle_resource(self, resource_action: dict, action_factory: dict):

        self._check_missing_fields(resource_action)

        log.info("Handle resource {}.".format(resource_action))

        func = self._get_action_func(resource_action, action_factory)
        if isinstance(func, dict):
            return func

        try:
            job_response = func(resource_action)

        except Exception as e:
            log.error("An error occurred in _handle_resource: " + repr(e))
            traceback.print_exc()
            return self._new_job_response(False, -1, str(e))

        return job_response

    def _get_action_func(self, resource_action: dict, action_factory: dict) -> any:
        action = action_factory.get(resource_action['action'], None)
        if not action:
            return self._unsupported_action_job_response(resource_action['action'])

        func = action.get(resource_action['resource'], None)
        if not func:
            return self._unsupported_resource_for_action_job_response(resource_action['resource'], resource_action['action'])

        return func

    @staticmethod
    def _check_missing_fields(resource_action: dict) -> None:
        for field in ['resource', 'action', 'id']:
            if field not in resource_action:
                raise MissingFieldException(field)

    def _remove_image(self, resource_action) -> dict:
        image_id = resource_action['id']
        try:
            response = self.docker_client.api.remove_image(image_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error(e)

        deleted_found = False
        untagged_found = False
        for r in response:
            if 'Deleted' in r and image_id in r['Deleted']:
                deleted_found = True
            if 'Untagged' in r and image_id in r['Untagged']:
                untagged_found = True

        if deleted_found:
            return self._new_job_response(True, 200, f"Image {self._clean_id(image_id)} deleted successfully")

        if untagged_found:
            return self._new_job_response(True, 200, f"Image {self._clean_id(image_id)} untagged successfully but not removed")

        return self._new_job_response(True, 200, "")

    def _pull_image(self, resource_action):
        image_id = resource_action['id']
        credential_id = resource_action.get('credential')
        log.info("Pull image {} with credentials {}.".format(image_id, credential_id))
        if credential_id:
            credential = self.job.context.get(credential_id)
            if credential:
                log.info("Credential retrieved: {}.".format(credential))
                infra_service_id = credential.get('parent')
                if infra_service_id:
                    infra_service = self.job.context.get(infra_service_id)
                    if infra_service:
                        log.info("Infra service retrieved: {}.".format(infra_service))
                        try:
                            if 'username' in credential and 'password' in credential and 'endpoint' in infra_service:
                                login_response = self.docker_client.api.login(credential['username'], credential['password'], None, infra_service['endpoint'])
                                log.info("Login result: {}.".format(login_response))
                            else:
                                log.warning("username, password or endpoint not specified")
                        except docker.errors.APIError as e:
                            return self._get_job_response_from_server_error(e)
                    else:
                        log.warning("infra_service not found in job context")
                else:
                    log.warning("credential parent not found")
            else:
                log.warning("credential not found in job context")

        try:
            response = self.docker_client.api.pull(image_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error(e)

        line = response.splitlines()[-1]
        if "Image is up to date" in line:
            return self._new_job_response(True, 200, f"Image {self._clean_id(image_id)} was already present and updated")

        if "Downloaded newer image" in line:
            return self._new_job_response(True, 200, f"Image {self._clean_id(image_id)} downloaded successfully")

        return self._new_job_response(True, 200, f"Image {self._clean_id(image_id)} successful pulled")

    def _remove_container(self, resource_action):
        container_id = resource_action['id']
        try:
            self.docker_client.api.remove_container(container_id)

        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error(e)

        return self._new_job_response(True, 204, f"Container {self._clean_id(container_id)} removed successfully")

    def _remove_volume(self, resource_action):
        volume_id = resource_action['id']
        try:
            self.docker_client.api.remove_volume(volume_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error(e)

        return self._new_job_response(True, 204, f"Volume {self._clean_id(volume_id)} removed successfully")

    def _remove_network(self, resource_action):
        network_id = resource_action['id']
        try:
            self.docker_client.api.remove_network(network_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error(e)

        return self._new_job_response(True, 204, f"Network {self._clean_id(network_id)} removed successfully")

    @staticmethod
    def _get_job_response_from_server_error(error: docker.errors.APIError) -> dict:
        return {
            'success': False,
            'return-code': error.response.status_code,
            'content': error.response.content.decode('utf-8'),
            'message': _extract_content_message(error.response.content)
        }

    @staticmethod
    def _clean_id(res_id: str) -> str:
        return res_id[:12] if is_sha256_hash(res_id) else res_id

def is_sha256_hash(s: str) -> bool:
    return bool(re.fullmatch(r'[a-fA-F0-9]{64}', s))

def _extract_content_message(content: bytes) -> str:
    try:
        data = json.loads(content)
        return data.get("message", content.decode('utf-8'))

    except Exception as _:
        return content.decode('utf-8')
