import json
import logging
from subprocess import CompletedProcess

from nuvla.job_engine.connector.connector import should_connect
from nuvla.job_engine.connector.k8s_driver import Kubernetes
from nuvla.job_engine.connector.utils import execute_cmd, create_tmp_file

log = logging.getLogger('helm_driver')


class Helm:
    """
    Class to interact with Helm CLI.
    """
    def __init__(self, path_to_k8s_creds: str, **kwargs):
        self.k8s = Kubernetes.from_path_to_k8s_creds(path_to_k8s_creds, **kwargs)
        log.debug(self.k8s)

    @property
    def connector_type(self):
        return 'Helm-cli'

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    def run_command_container(self, command: str, job_name: str,
                              backoff_limit=0,
                              namespace=None) -> CompletedProcess:
        """
        Generic to run a container with a helm command as Kubernetes Job.
        """

        helm_image = self.k8s.base_image
        log.debug('The helm image is set to: %s', helm_image)

        ttl_sec = 60  # FIXME: for production, once thoroughly tested this should be set to 1 or so

        helm_manifest = f'''apiVersion: batch/v1
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
'''

        log.debug('Helm Job YAML %s ', helm_manifest)

        result = self.k8s.apply_manifest(helm_manifest)
        if result.returncode == 1:
            raise Exception(f'Failed to run helm command: {result.stderr}')

        self.k8s.wait_job_succeeded(job_name, namespace)

        return result

    @should_connect
    def run_command(self, command: list) -> CompletedProcess:
        """
        Generic to run a container with a Helm command.
        """

        cmd = ['helm',
               '--kubeconfig', self.k8s.kubeconfig()] \
            + command

        log.debug('Helm command to run %s ', cmd)

        return execute_cmd(cmd)

    def _from_absolute_url(self, op: str, release: str,
                           absolute_url: str, namespace: str, values_yaml=None):
        cmd = [op, release, absolute_url,
               '--namespace', namespace]

        if op == 'install' and namespace:
            cmd += ['--create-namespace']

        values_yaml_fd = None
        if values_yaml:
            values_yaml_fd = create_tmp_file(values_yaml)
            cmd += ['--values', values_yaml_fd.name]
        result = self.run_command(cmd)
        log.debug('Helm %s command result: %s', op, result)
        if values_yaml_fd:
            values_yaml_fd.close()
        return result

    def _from_helm_repo_cred(self, op, helm_repo, helm_repo_cred, chart_name,
                             version, values_yaml, helm_release, namespace):
        repo_name = 'helm-repo'

        repos_config = f"""
apiVersion: ""
generated: "0001-01-01T00:00:00Z"
repositories:
- caFile: ""
  certFile: ""
  insecure_skip_tls_verify: false
  keyFile: ""
  name: {repo_name}
  pass_credentials_all: false
  url: {helm_repo}
  username: {helm_repo_cred['username']}
  password: {helm_repo_cred['password']}
"""
        repos_config_fd = create_tmp_file(repos_config)

        result = self.run_command(['repo', 'update',
                                   '--repository-config', repos_config_fd.name])
        log.debug('Helm repo update command result: %s', result)

        cmd = [op, helm_release,
               f'{repo_name}/{chart_name}',
               '--repository-config', repos_config_fd.name,
               '--namespace', namespace]

        if op == 'install' and namespace:
            cmd += ['--create-namespace']

        if version:
            cmd += ['--version', version]

        values_yaml_fd = None
        if values_yaml:
            values_yaml_fd = create_tmp_file(values_yaml)
            cmd += ['--values', values_yaml_fd.name]

        try:
            result = self.run_command(cmd)
            log.debug('Helm %s command result: %s', op, result)
        except Exception as e:
            log.error(f'Error running helm {op}: {e}')
            raise e
        else:
            if repos_config_fd:
                repos_config_fd.close()
            if values_yaml_fd:
                values_yaml_fd.close()

        return result

    def op_install_upgrade(self, op, helm_release, helm_repo_url, helm_repo_cred,
                           helm_absolute_url, chart_name, version, namespace,
                           values_yaml):
        if helm_absolute_url:
            result = self._from_absolute_url(op, helm_release,
                                             helm_absolute_url, namespace)
        elif helm_repo_cred:
            result = self._from_helm_repo_cred(op, helm_repo_url, helm_repo_cred,
                                               chart_name, version, values_yaml,
                                               helm_release, namespace)
        else:
            cmd = [op, '--repo', helm_repo_url,
                   helm_release, chart_name,
                   '--namespace', namespace]
            if op == 'install' and namespace:
                cmd += ['--create-namespace']
            if version:
                cmd += ['--version', version]
            values_yaml_fd = None
            if values_yaml:
                values_yaml_fd = create_tmp_file(values_yaml)
                cmd += ['--values', values_yaml_fd.name]
            result = self.run_command(cmd)
            log.debug('Helm %s command result: %s', op, result)
            if values_yaml_fd:
                values_yaml_fd.close()
        return result

    def install(self, helm_repo, helm_release, chart_name, namespace,
                version=None, helm_repo_cred=dict, helm_absolute_url=None,
                chart_values_yaml=None) -> CompletedProcess:
        return self.op_install_upgrade('install', helm_release, helm_repo,
                                       helm_repo_cred, helm_absolute_url,
                                       chart_name, version, namespace,
                                       chart_values_yaml)

    def upgrade(self, helm_repo, helm_release, chart_name, namespace,
                version=None, helm_repo_cred=dict, helm_absolute_url=None,
                chart_values_yaml=None) -> CompletedProcess:
        return self.op_install_upgrade('upgrade', helm_release, helm_repo,
                                       helm_repo_cred, helm_absolute_url,
                                       chart_name, version, namespace,
                                       chart_values_yaml)

    def uninstall(self, helm_release, namespace) -> CompletedProcess:
        cmd = ['uninstall', helm_release, '--namespace', namespace]
        result = self.run_command(cmd)
        try:
            self.k8s.delete_namespace(namespace)
        except Exception as e:
            log.error(f'Error deleting namespace {namespace}: {e}')
        return result

    def list(self, namespace, all=False, release=None) -> dict:
        cmd = ['list', '--namespace', namespace, '-o', 'json']
        if all:
            cmd += ['--all']
        if release:
            cmd += ['-f', release]
        return json.loads(self.run_command(cmd).stdout)
