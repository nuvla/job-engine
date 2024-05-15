import json
import logging
from subprocess import CompletedProcess

from nuvla.job_engine.connector.connector import should_connect
from nuvla.job_engine.connector.k8s_driver import Kubernetes
from nuvla.job_engine.connector.utils import execute_cmd

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
                           absolute_url: str, namespace: str):
        cmd = [op, release, absolute_url,
               '--namespace', namespace]
        result = self.run_command(cmd)
        log.debug('Helm %s command result: %s', op, result)
        return result

    def _op_install_upgrade(self, op, chart_name, helm_absolute_url,
                            helm_release, helm_repo, helm_repo_cred, namespace,
                            version):
        if helm_absolute_url:
            result = self._from_absolute_url(op, helm_release,
                                             helm_absolute_url, namespace)
        elif helm_repo_cred:
            repo_name = 'helm-repo'

            # FIXME: username and password need to go to a config file.
            cmd = ['repo', 'add', repo_name, helm_repo,
                   '--username', helm_repo_cred['username'],
                   '--password', helm_repo_cred['password']]
            result = self.run_command(cmd)
            log.debug('Helm repo add command result: %s', result)

            result = self.run_command(['repo', 'update'])
            log.debug('Helm repo update command result: %s', result)

            cmd = [op, helm_release,
                   f'{repo_name}/{chart_name}',
                   '--namespace', namespace]
            if version:
                cmd += ['--version', version]
            result = self.run_command(cmd)
            log.debug('Helm install command result: %s', result)
            try:
                cmd = ['repo', 'remove', repo_name]
                res = self.run_command(cmd)
                log.debug('Helm repo remove command result: %s', res)
            except Exception as e:
                log.error(f'Error removing helm repo {repo_name}: {e}')
        else:
            cmd = [op, '--repo', helm_repo,
                   helm_release, chart_name,
                   '--namespace', namespace]
            if version:
                cmd += ['--version', version]
            result = self.run_command(cmd)
            log.debug('Helm %s command result: %s', op, result)
        return result

    def install(self, helm_repo, helm_release, chart_name, namespace,
                version=None, registries_auth=list, helm_repo_cred=dict,
                helm_absolute_url=None) -> CompletedProcess:
        self.k8s.create_namespace(namespace, exists_ok=True)

        if registries_auth:
            self.k8s.add_secret_image_registries_auths(registries_auth,
                                                       namespace)

        result = self._op_install_upgrade('install', chart_name,
                                          helm_absolute_url,
                                          helm_release, helm_repo,
                                          helm_repo_cred, namespace, version)
        return result

    def upgrade(self, helm_repo, helm_release, chart_name, namespace,
                version=None, helm_repo_cred=dict, helm_absolute_url=None) -> \
            CompletedProcess:

        # TODO: check we might need this.
        # if registries_auth:
        #     self.k8s.add_secret_image_registries_auths(registries_auth,
        #                                                namespace)

        return self._op_install_upgrade('upgrade', chart_name,
                                        helm_absolute_url,
                                        helm_release, helm_repo,
                                        helm_repo_cred, namespace,
                                        version)

    def _service_account_roles(self, namespace):
        roles_manifest = f'''
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: {namespace}
  name: serviceaccount-getter
rules:
- apiGroups: [""]
  resources: ["*"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: serviceaccount-getter-binding
  namespace: {namespace}
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
roleRef:
  kind: Role
  name: serviceaccount-getter
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: {namespace}
  name: secret-creator
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secret-creator-binding
  namespace: {namespace}
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
roleRef:
  kind: Role
  name: secret-creator
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: {namespace}
  name: resource-creator
rules:
- apiGroups: [""]
  resources: ["serviceaccounts", "services"]
  verbs: ["create"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: resource-creator-binding
  namespace: {namespace}
subjects:
- kind: ServiceAccount
  name: default
  namespace: default 
roleRef:
  kind: Role
  name: resource-creator
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: {namespace}
  name: deployment-getter
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deployment-getter-binding
  namespace: {namespace}
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
roleRef:
  kind: Role
  name: deployment-getter
  apiGroup: rbac.authorization.k8s.io
'''
        result = self.k8s.apply_manifest(roles_manifest)
        log.debug(f'service account roles install result: {result}')

    def _service_account_clusterroles(self, namespace):
        the_manifest = f'''
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: namespace-creator
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: namespace-creator-binding
subjects:
- kind: ServiceAccount
  name: default
  namespace: {namespace}
roleRef:
  kind: ClusterRole
  name: namespace-creator
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: namespace-creator
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: namespace-creator-binding
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
roleRef:
  kind: ClusterRole
  name: namespace-creator
  apiGroup: rbac.authorization.k8s.io
'''
        result = self.k8s.apply_manifest(the_manifest)
        log.info(f'service account clusterroles install result: {result}')

    def uninstall(self, helm_release, namespace) -> CompletedProcess:
        cmd = ['uninstall', helm_release, '--namespace', namespace]
        result = self.run_command(cmd)
        try:
            self.k8s.delete_namespace(namespace)
        except Exception as e:
            log.error(f'Error deleting namespace {namespace}: {e}')
        return result

    def list(self, namespace, all=False) -> dict:
        cmd = ['list', '--namespace', namespace, '-o', 'json']
        if all:
            cmd += ['--all']
        return json.loads(self.run_command(cmd).stdout)

