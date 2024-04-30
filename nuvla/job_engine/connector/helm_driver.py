import logging
from subprocess import CompletedProcess

from nuvla.job_engine.connector.connector import should_connect
from nuvla.job_engine.connector.k8s_driver import Kubernetes

log = logging.getLogger('helm_driver')
log.setLevel(logging.DEBUG)


class Helm:
    def __init__(self, path_to_k8s_creds: str, **kwargs):
        self.k8s = Kubernetes.from_path_to_k8s_creds(path_to_k8s_creds,
                                                     **kwargs)
        self.k8s.state_debug()

    @property
    def connector_type(self):
        return 'Helm-cli'

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    @should_connect
    def run_command(self, command: str, job_name: str, backoff_limit=0,
                    namespace=None) -> CompletedProcess:
        """
        Generic to run a container with a helm command as Kubernetes Job.
        """

        helm_image = self.k8s.base_image
        log.debug('The helm image is set to: %s', helm_image)

        ttl_sec = 60  # FIXME: for production, once thoroughly tested this should be set to 1 or so

        helm_manifest = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
spec:
  ttlSecondsAfterFinished: {ttl_sec}
  backoffLimit: {backoff_limit}
  template:
    spec:
      containers:
      - name: {job_name}
        image: {helm_image}
        ports:
        env:
        - name: HOST_NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        command: ['sh', '-c', '{command}']
      restartPolicy: Never
"""

        log.debug('Helm Job YAML %s ', helm_manifest)

        result = self.k8s.apply_manifest(helm_manifest)
        if result.returncode == 1:
            raise Exception(f'Failed to run helm command: {result.stderr}')

        self.k8s.wait_job_succeeded(job_name, self.k8s.namespace)

        return result

    def install(self, helm_repo, helm_release, chart_name, namespace):
        job_name = self.k8s.create_object_name('helm-install')
        cmd = ['helm', 'install',
               '--repo', helm_repo,
               helm_release, chart_name,
               '--namespace', 'default', '--create-namespace']
        result = self.run_command(' '.join(cmd), job_name)
        log.info(f'Helm install result: {result}')
