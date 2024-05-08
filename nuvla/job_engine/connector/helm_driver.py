import logging
from subprocess import CompletedProcess

from nuvla.job_engine.connector.connector import should_connect
from nuvla.job_engine.connector.k8s_driver import Kubernetes

log = logging.getLogger('helm_driver')
log.setLevel(logging.DEBUG)


class Helm:
    def __init__(self, path_to_k8s_creds: str):
        self.k8s = Kubernetes.from_path_to_k8s_creds(path_to_k8s_creds)
        self.k8s.state_debug()

    @property
    def connector_type(self):
        return 'Helm-cli'

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    @should_connect
    def run_command(self, command: str, job_name: str, backoff_limit=0) -> CompletedProcess:
        """
        Generic to run a container with a helm command as Kubernetes Job.
        """

        helm_image = self.k8s.base_image
        log.debug('The helm image is set to: %s', helm_image)

        kube_config = "/root/.kube/config"
        host_kube_config = "/root/.kube"
        host_helm_config = "/root/.config/helm"
        host_helm_cache = "/root/.cache/helm"
        host_deployment_path = "/root/deployment"

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
        - name: KUBECONFIG
          value: {kube_config}
        command: ['sh', '-c', '{command}']
        volumeMounts:
        - name: kube-config
          mountPath: /root/.kube
        - name: helm-config
          mountPath: /root/.config/helm
        - name: helm-cache
          mountPath: /root/.cache/helm
        - name: deployment-path
          mountPath: /root/deployment
      volumes:
      - name: kube-config
        hostPath:
          path: {host_kube_config}
      - name: helm-config
        hostPath:
          path: {host_helm_config}
      - name: helm-cache
        hostPath:
          path: {host_helm_cache}
      - name: deployment-path
        hostPath:
          path: {host_deployment_path}
      restartPolicy: Never
"""

        logging.debug('Helm Job YAML %s ', helm_manifest)

        result = self.k8s.apply_manifest(helm_manifest)

        self.k8s.wait_job_succeeded(job_name, self.k8s.namespace)

        return result

    def repo_update(self):
        job_name = self.k8s.create_object_name('helm-repo-update')
        cmd = 'helm repo update'
        result = self.run_command(cmd, job_name)
        log.info(f'Helm update result: {result}')
