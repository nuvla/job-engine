import requests


DEFAULT_TIMEOUT = 30
DEFAULT_HEADERS = {'X-Nuvla-Mm3-Caller': 'job-engine'}
MM3_LIFECYCLE_BASE_PATH = '/mm3/app_lcm/v1'
MM3_LIFECYCLE_APP_INSTANCES_PATH = f'{MM3_LIFECYCLE_BASE_PATH}/app_instances'
MM3_LIFECYCLE_OP_OCCS_PATH = f'{MM3_LIFECYCLE_BASE_PATH}/app_lcm_op_occs'


class Mm3ClientError(RuntimeError):
    pass


class Mm3Client:
    def __init__(self, endpoint: str, verify: bool = True, timeout: int = DEFAULT_TIMEOUT):
        self.endpoint = endpoint.rstrip('/')
        self.verify = verify
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None):
        url = f'{self.endpoint}{path}'
        response = requests.request(method,
                                    url,
                                    json=payload,
                                    headers=DEFAULT_HEADERS,
                                    timeout=self.timeout,
                                    verify=self.verify)
        if response.status_code < 200 or response.status_code >= 300:
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise Mm3ClientError(f'Mm3 request failed: {method} {url} -> '
                                 f'{response.status_code} {body}')

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def create_app_instance(self, payload: dict):
        return self._request('post', MM3_LIFECYCLE_APP_INSTANCES_PATH, payload)

    def get_app_instance(self, app_instance_id: str):
        return self._request('get', f'{MM3_LIFECYCLE_APP_INSTANCES_PATH}/{app_instance_id}')

    def delete_app_instance(self, app_instance_id: str):
        return self._request('delete', f'{MM3_LIFECYCLE_APP_INSTANCES_PATH}/{app_instance_id}')

    def operate_app_instance(self, app_instance_id: str, change_state_to: str):
        return self._request('post',
                             f'{MM3_LIFECYCLE_APP_INSTANCES_PATH}/{app_instance_id}/operate',
                             {'changeStateTo': change_state_to})
