import docker
import docker.errors


class MissingFieldException(Exception):
    def __init__(self, field):
        self.field = field
        super().__init__(f"Missing field: {field}")


class DockerCoeResources:
    def __init__(self):
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

        func = self._get_action_func(resource_action, action_factory)
        if isinstance(func, dict):
            return func

        try:
            job_response = func(resource_action['id'])

        except Exception as e:
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

    def _remove_image(self, image_id) -> dict:
        try:
            response = self.docker_client.api.remove_image(image_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error('image', e, image_id)

        deleted_found = False
        untagged_found = False
        for r in response:
            if 'Deleted' in r and image_id in r['Deleted']:
                deleted_found = True
            if 'Untagged' in r and image_id in r['Untagged']:
                untagged_found = True

        if deleted_found:
            return self._new_job_response(True, 200, f"Image {image_id} deleted successfully")

        if untagged_found:
            return self._new_job_response(True, 200, f"Image {image_id} untagged successfully but not removed")

        return self._new_job_response(True, 200, "")

    def _pull_image(self, image_id):
        try:
            response = self.docker_client.api.pull(image_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error('image', e, image_id)

        line = response.splitlines()[-1]
        if "Image is up to date" in line:
            return self._new_job_response(True, 200, f"Image {image_id} was already present and updated")

        if "Downloaded newer image" in line:
            return self._new_job_response(True, 200, f"Image {image_id} downloaded successfully")

        return self._new_job_response(True, 200, "Image pull successful")

    def _remove_container(self, container_id):
        try:
            self.docker_client.api.remove_container(container_id)

        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error('container', e, container_id)

        return self._new_job_response(True, 204, f"Container {container_id} removed successfully")

    def _remove_volume(self, volume_id):
        try:
            self.docker_client.api.remove_volume(volume_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error('volume', e, volume_id)

        return self._new_job_response(True, 204, f"Volume {volume_id} removed successfully")

    def _remove_network(self, network_id):
        try:
            self.docker_client.api.remove_network(network_id)
        except docker.errors.APIError as e:
            return self._get_job_response_from_server_error('network', e, network_id)

        return self._new_job_response(True, 204, f"Network {network_id} removed successfully")

    @staticmethod
    def _get_job_response_from_server_error(resource: str, error: docker.errors.APIError, resource_id: str) -> dict:
        job_response = {
            'success': False,
            'return-code': error.response.status_code,
            'content': str(error)
        }

        match error.response.status_code:
            case 403:
                # Only for Network delete operation
                job_response['message'] = f"Operation not supported for {resource} -- {resource_id}"
            case 404:
                job_response['message'] = f"{resource} -- {resource_id} not found"
            case 409:
                job_response['message'] = f"{resource} is in use. Cannot remove it."
            case 500:
                job_response['message'] = f"Server Error {resource} -- {resource}"
            case _:
                job_response['message'] = f"Unknown error: {error.response.text}"

        return job_response