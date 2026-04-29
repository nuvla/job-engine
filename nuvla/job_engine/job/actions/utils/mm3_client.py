import requests


DEFAULT_TIMEOUT = 30


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
        return self._request('post', '/mm3/app-instances', payload)

    def get_app_instance(self, app_instance_id: str):
        return self._request('get', f'/mm3/app-instances/{app_instance_id}')

    def delete_app_instance(self, app_instance_id: str):
        return self._request('delete', f'/mm3/app-instances/{app_instance_id}')

    def operate_app_instance(self, app_instance_id: str, change_state_to: str):
        return self._request('post',
                             f'/mm3/app-instances/{app_instance_id}/operate',
                             {'changeStateTo': change_state_to})
