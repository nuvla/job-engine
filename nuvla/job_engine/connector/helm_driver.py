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

    @should_connect
    def run_command(self, command: str, 
                    job_name: str,
                    namespace=None, 
                    backoff_limit=0
                    ) -> CompletedProcess:
        """
        Generic to run a container with a helm command as Kubernetes Job.
        """

        helm_image = self.k8s.base_image
        log.debug('The helm image is set to: %s', helm_image)

        ttl_sec = 60  # FIXME: for production, once thoroughly tested this should be set to 1 or so

        print(f'\nThe command is:\n {command}')

        helm_manifest = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  ## namespace: {namespace}
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

        print(f'Helm Job YAML\n\n {helm_manifest}')

        result = self.k8s.apply_manifest(helm_manifest)
        if result.returncode == 1:
            raise Exception(f'Failed to run helm command: {result.stderr}')
            return result
        # needs to be parameterized
        self.k8s.wait_job_succeeded(job_name, namespace)

        return result

    @should_connect
    def install(self, helm_repo, helm_release, chart_name, namespace):
        job_name = self.k8s.create_object_name('helm-install')
        print(f'\nThe namespace is thought to be: {namespace}\nAnd the job name is: {job_name}\n')
        create_ns_cmd = self.k8s.build_cmd_line(['create', 'ns', namespace])
        execute_cmd(create_ns_cmd)
        helm_service_acct_roles = self.service_account_roles(namespace)
        helm_service_acct_clusterroles = self.service_account_clusterroles(namespace)

        cmd = ['helm', 'install',
               '--repo', helm_repo,
               helm_release, chart_name,
               '--namespace', namespace, '--create-namespace']
        result = self.run_command(' '.join(cmd), job_name, self.k8s.namespace)
        print(f'Helm install result {result}')
        log.info(f'Helm install result: {result}')

    def service_account_roles(self, namespace):
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
        # print(f'{roles_manifest}')
        roles_result = self.k8s.apply_manifest(roles_manifest)
        # print(f'service accounts: install result {roles_result}')
        log.info(f'service accounts: install result: {roles_result}')

    def service_account_clusterroles(self, namespace):
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
        # print(f'{the_manifest}')
        roles_result = self.k8s.apply_manifest(the_manifest)
        # print(f'service accounts: install result {roles_result}')
        log.info(f'service accounts: install result: {roles_result}')
       
