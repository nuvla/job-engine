import base64
import json
import logging
import os
import random
import string
import time
from datetime import datetime
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from typing import List, Dict

import yaml

from nuvla.job_engine.connector.connector import should_connect
from nuvla.job_engine.connector.utils import create_tmp_file, execute_cmd, \
    join_stderr_stdout, generate_registry_config

log = logging.getLogger('k8s_driver')
log.setLevel(logging.DEBUG)


def get_pem_content(path, name):
    with open(f'{path}/{name}.pem', encoding='utf8') as fd:
        content = fd.read()
    return content


def get_kubernetes_local_endpoint():
    kubernetes_host = os.getenv('KUBERNETES_SERVICE_HOST')
    kubernetes_port = os.getenv('KUBERNETES_SERVICE_PORT')
    if kubernetes_host and kubernetes_port:
        return f'https://{kubernetes_host}:{kubernetes_port}'
    return ''


def manifest_interpolate_env_vars(manifest: str, env: dict) -> str:
    envsubst_shell_format = ' '.join([f'${k}' for k in env.keys()])
    cmd = ['envsubst', envsubst_shell_format]
    return execute_cmd(cmd, env=env, input=manifest).stdout


class Kubernetes:

    K8S_JOB = 'job.batch/'

    def __init__(self, **kwargs):

        # Mandatory kwargs
        self.ca = kwargs['ca']
        self.cert = kwargs['cert']
        self.key = kwargs['key']

        self.endpoint = kwargs['endpoint']

        self.ca_file = None
        self.cert_file = None
        self.key_file = None

        self._namespace = None

        self.ne_image_registry = os.getenv('NE_IMAGE_REGISTRY', '')
        self.ne_image_org = os.getenv('NE_IMAGE_ORGANIZATION', 'sixsq')
        self.ne_image_repo = os.getenv('NE_IMAGE_REPOSITORY', 'nuvlaedge')
        self.ne_image_tag = os.getenv('NE_IMAGE_TAG', 'latest')
        self.ne_image_name = os.getenv('NE_IMAGE_NAME',
                                       f'{self.ne_image_org}/{self.ne_image_repo}')
        self.base_image = f'{self.ne_image_registry}{self.ne_image_name}:{self.ne_image_tag}'

    @staticmethod
    def from_path_to_k8s_creds(path_to_k8s_creds: str):
        return Kubernetes(**{
                'cert': get_pem_content(path_to_k8s_creds, 'cert'),
                'key': get_pem_content(path_to_k8s_creds, 'key'),
                'ca': get_pem_content(path_to_k8s_creds, 'ca'),
                'endpoint': get_kubernetes_local_endpoint()})

    def state_debug(self):
        log.debug('Kubernetes object state:')
        log.debug('CA file %s ', self.ca)
        log.debug('User certificate file %s ', self.cert)
        log.debug('User key file %s ', self.key)
        log.debug('Endpoint %s ', self.endpoint)

    @property
    def connector_type(self):
        return 'Kubernetes-cli'

    def connect(self):
        log.info(f'Kubernetes endpoint: {self.endpoint}')
        self.ca_file = create_tmp_file(self.ca)
        self.cert_file = create_tmp_file(self.cert)
        self.key_file = create_tmp_file(self.key)

    def clear_connection(self, _connect_result):
        if self.ca_file:
            self.ca_file.close()
            self.ca_file = None
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def build_cmd_line(self, cmd: list) -> list:
        """
        Build the kubectl command line

        Arguments:
           cmd: a list containing the kubectl command line and arguments
        """
        return ['kubectl', '-s', self.endpoint,
                '--client-certificate', self.cert_file.name,
                '--client-key', self.key_file.name,
                '--certificate-authority', self.ca_file.name] \
            + cmd

    @staticmethod
    def create_object_name(job_name, k=5):
        """
        Create the job name with random string attached
        """
        return job_name + "-" + ''.join(random.choices(string.digits, k=k))

    @should_connect
    def apply_manifest(self, manifest: str, namespace: str = None) -> CompletedProcess:
        """
        Runs `manifest` in a temporary directory.
        Raises exception if running manifest fails.
        """
        with TemporaryDirectory() as tmp_dir_name:
            manifest_path = os.path.join(tmp_dir_name, 'manifest.txt')
            with open(manifest_path, 'w', encoding='utf-8') as fp:
                fp.write(manifest)
            cmd = ['apply', '-f', manifest_path]
            if namespace:
                cmd = ['-n', namespace] + cmd
            result = execute_cmd(self.build_cmd_line(cmd))
            log.debug('The result of applying manifest: %s', result)

        return result

    @should_connect
    def apply_manifest_with_context(self, manifest: str, namespace, env: dict,
                                    files: List[dict],
                                    registries_auth: list) -> CompletedProcess:
        if env:
            manifest = manifest_interpolate_env_vars(manifest, env)

        common_labels = {'nuvla.application.name': namespace,
                         'nuvla.deployment.uuid': env['NUVLA_DEPLOYMENT_UUID']}
        if 'NUVLA_DEPLOYMENT_GROUP_UUID' in env:
            common_labels.update(
                {'nuvla.deployment-group.uuid': env['NUVLA_DEPLOYMENT_GROUP_UUID']})

        with TemporaryDirectory() as dir_name:
            self._create_deployment_context(dir_name,
                                            namespace,
                                            manifest,
                                            files,
                                            registries_auth,
                                            common_labels)

            cmd_deploy = self.build_cmd_line(['apply', '-k', dir_name])

            return execute_cmd(cmd_deploy)

    @should_connect
    def read_job_log(self, job_name: str) -> CompletedProcess:
        """
        Read the log of a kubernetes batch job.

        vars:
         job_name: the name of the job
        :return CompletedProcess object
        """

        return self._get_workload_log(self.K8S_JOB + job_name)

    def _get_workload_log(self, workload_name: str) -> CompletedProcess:
        read_log_cmd = self.build_cmd_line(['logs', workload_name])
        log_result = execute_cmd(read_log_cmd)
        log.debug('The logs of %s: %s', workload_name,
                  log_result.stdout)
        return log_result

    @staticmethod
    def get_all_namespaces_from_manifest(manifest: str) -> set:
        namespaces = set()
        try:
            for doc in yaml.safe_load_all(manifest):
                ns = doc.get('metadata', {}).get('namespace', '')
                if ns:
                    namespaces.add(ns)
        except Exception as ex:
            log.error('Failed to extract namespaces from manifest: %s', ex)
        return namespaces

    @staticmethod
    def _create_deployment_context(directory_path, namespace, manifest,
                                   files, registries_auth: list,
                                   common_labels: Dict[str, str] = None):
        manifest_file_path = directory_path + '/manifest.yml'
        with open(manifest_file_path, 'w') as manifest_file:
            manifest_file.write(manifest)

        namespace_file_path = directory_path + '/namespace.yml'
        with open(namespace_file_path, 'w') as namespace_file:
            namespace_data = {'apiVersion': 'v1',
                              'kind': 'Namespace',
                              'metadata': {'name': namespace}}
            log.debug('Namespace data: %s', namespace_data)
            yaml.safe_dump(namespace_data, namespace_file, allow_unicode=True)

        # NB! We have to place the objects from the manifest into a namespace,
        # otherwise we will get them deployed into the namespace of the job.
        kustomization_data = {'namespace': namespace,
                              'commonLabels': common_labels,
                              'resources': ['manifest.yml', 'namespace.yml']}

        if files:
            for file_info in files:
                file_path = directory_path + "/" + file_info['file-name']
                f = open(file_path, 'w')
                f.write(file_info['file-content'])
                f.close()

        if registries_auth:
            config = generate_registry_config(registries_auth)
            config_b64 = base64.b64encode(config.encode('ascii')).decode(
                'utf-8')
            secret_registries_fn = 'secret-registries-credentials.yml'
            secret_registries_path = os.path.join(directory_path,
                                                  secret_registries_fn)
            with open(secret_registries_path, 'w') as secret_registries_file:
                secret_registries_data = {'apiVersion': 'v1',
                                          'kind': 'Secret',
                                          'metadata': {
                                              'name': 'registries-credentials'},
                                          'data': {
                                              '.dockerconfigjson': config_b64},
                                          'type': 'kubernetes.io/dockerconfigjson'}
                yaml.safe_dump(secret_registries_data, secret_registries_file,
                               allow_unicode=True)
            kustomization_data.setdefault('resources', []) \
                .append(secret_registries_fn)

        log.debug('Kustomization data: %s', kustomization_data)

        kustomization_file_path = directory_path + '/kustomization.yml'
        with open(kustomization_file_path, 'w') as fd:
            yaml.safe_dump(kustomization_data, fd, allow_unicode=True)

    @should_connect
    def delete_namespace(self, namespace: str) -> CompletedProcess:
        cmd = self.build_cmd_line(['delete', 'namespace', namespace])
        log.debug('Command line to delete namespace: %s', cmd)
        return execute_cmd(cmd)

    @should_connect
    def delete_all_resources_by_label(self, label: str) -> CompletedProcess:
        cmd = self.build_cmd_line(
            ['delete', 'all', '--all-namespaces', '-l', label])
        log.debug('Command line to delete all resources by label: %s', cmd)
        return execute_cmd(cmd)

    @should_connect
    def get_namespace_objects(self, namespace, objects: list):
        if not namespace:
            msg = 'Namespace is not provided.'
            log.error(msg)
            raise ValueError(msg)

        what = objects and ','.join(objects) or 'all'

        cmd_stop = self.build_cmd_line(['-n', namespace, 'get', what,
                                        '-o', 'json'])

        try:
            return execute_cmd(cmd_stop).stdout
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                return f'Namespace "{namespace}" not found.'
            else:
                raise ex

    TIMESTAMP_FMT_UTC = '%Y-%m-%dT%H:%M:%S.%f000Z'

    @classmethod
    def _timestamp_now_utc(cls) -> str:
        time_now = datetime.timestamp(datetime.now())
        utc_timestamp = datetime.utcfromtimestamp(time_now)
        return utc_timestamp.strftime(cls.TIMESTAMP_FMT_UTC)

    def _build_logs_cmd(self,
                        namespace: str,
                        pod_unique_id: str,
                        container_name: str,
                        since: datetime,
                        tail_lines: int) -> list:

        container_opts = [f'pod/{pod_unique_id}',
                          f'--container={container_name}']

        list_opts_log = ['--timestamps=true',
                         '--tail', str(tail_lines),
                         '--namespace', namespace]
        if since:
            list_opts_log.extend(['--since-time', since.isoformat()])

        return self.build_cmd_line(['logs'] + container_opts + list_opts_log)

    @should_connect
    def _get_container_logs(self,
                            namespace,
                            pod: dict,
                            since: datetime,
                            tail_lines: int = 10) -> str:
        """
        Given `pod` definition in a `namespace`, returns `tail_lines` log lines
        from `since` date per each container found in the `pod` .

        :param namespace: str
        :param pod: dict
        :param since: datetime
        :param tail_lines: int
        :return: str
        """
        pod_logs = ''
        pod_unique_id = pod['metadata']['name']
        log.debug('Working with pod: %s', pod_unique_id)

        for container in pod['spec']['containers']:
            container_name = container['name']
            log.debug('Working with container: %s', container_name)

            cmd = self._build_logs_cmd(namespace,
                                       pod_unique_id,
                                       container_name,
                                       since,
                                       tail_lines)
            log.debug('Logs command line: %s', cmd)

            pod_container = f'pod/{pod_unique_id}->{container_name}'

            try:
                container_logs = execute_cmd(cmd).stdout
            except Exception as ex:
                log.error('Failed getting logs from %s: %s', pod_container, ex)
                continue

            if container_logs:
                pod_logs += \
                    f'\nLog last {tail_lines} lines for container ' \
                    f'{pod_container}' \
                    f'\n{container_logs}'
            else:
                pod_logs += \
                    f'\n{self._timestamp_now_utc()}' \
                    f' There are no log entries for {pod_container}' \
                    f' since {since.isoformat()}'
        return pod_logs

    def _get_pods_logs(self,
                       namespace,
                       pods: list,
                       since: datetime,
                       num_lines: int) -> str:

        logs_strings = []
        for pod in pods:
            log.debug('Get logs from pod: %s', pod)
            if pod["kind"] == 'Pod':
                logs = self._get_container_logs(namespace,
                                                pod,
                                                since,
                                                num_lines)
                logs_strings.append(logs)

        log.debug('Final log string: %s', logs_strings)

        return '\n'.join(logs_strings)

    @staticmethod
    def _filter_objects_owned(objects: list,
                              kind: str,
                              owner_kind: str,
                              owner_name: str) -> list:
        """
        Given list of `objects` and desired object `kind`, returns list of
        the object kinds that are owned by the object with kind `owner_kind`
        and name `owner_name`.

        :param objects: list
        :param kind: str
        :param owner_kind: str
        :param owner_name: str
        :return: list
        """
        log.debug('Filtering for Kind: %s owner_kind: %s owner_name: %s',
                  kind, owner_kind, owner_name)
        component_pods = []
        for obj in objects:
            log.debug('Current object: %s and obj kind: %s', obj,
                      obj['kind'])
            if obj['kind'] == kind and 'ownerReferences' in obj['metadata']:
                owner = obj['metadata']['ownerReferences'][0]
                if owner_kind == owner['kind'] and owner_name == owner['name']:
                    component_pods.append(obj)
        return component_pods

    def _exec_stdout_json(self, cmd_params) -> {}:
        cmd = self.build_cmd_line(cmd_params)
        log.debug('created JSON command: %s', cmd)
        cmd_out = execute_cmd(cmd)
        if cmd_out.stderr:
            log.warning('JSON command stderr gives: %s', cmd_out.stderr)

        return json.loads(cmd_out.stdout)

    @should_connect
    def _get_pods_cronjob(self, namespace, obj_name) -> list:
        # Find Jobs associated with the CronJob and get its name.
        kind_top_level = 'CronJob'
        pods_owner_kind = 'Job'
        jobs = self._exec_stdout_json(['get', pods_owner_kind,
                                       '-o', 'json',
                                       '--namespace', namespace])
        jobs_owned_by_cronjob = self._filter_objects_owned(
            jobs.get('items', []),
            pods_owner_kind,
            kind_top_level,
            obj_name)
        if len(jobs_owned_by_cronjob) < 1:
            log.error(f'Failed to find {pods_owner_kind} owned by '
                      f'{kind_top_level}/{obj_name}.')
            return []

        jobs_names = [x['metadata']['name'] for x in jobs_owned_by_cronjob]

        # Find Pods owned by the Jobs.
        pods = []
        all_pods = self._exec_stdout_json(['get', 'pods',
                                           '-o', 'json',
                                           '--namespace', namespace])
        for pods_owner_name in jobs_names:
            res = self._filter_objects_owned(all_pods['items'],
                                             'Pod', pods_owner_kind,
                                             pods_owner_name)
            pods.extend(res)
        return pods

    @staticmethod
    def valid_replica_set(replica_list: list):
        """
        Check that the current replica set is valid
        i.e. the required values are 1 and not 0!!
        in general we want the observedGeneration to be one
        and replicas to be not equal to zero
        """
        valid_replica_sets = []
        for replica in replica_list:
            test1 = replica['status']['replicas']
            if test1 != 0:
                log.debug(f"found valid_replica_set: my variable: {replica}")
                valid_replica_sets.append(replica)

        return valid_replica_sets

    @should_connect
    def _get_pods_deployment(self, namespace, obj_name) -> list:
        """
        Find the valid ReplicaSet associated with the Deployment and get its name.
        """
        kind_top_level = 'Deployment'
        pods_owner_kind = 'ReplicaSet'

        replica_sets = self._exec_stdout_json(['get', pods_owner_kind,
                                               '-o', 'json',
                                               '--namespace', namespace])

        owned_rep_sets = self._filter_objects_owned(
            replica_sets.get('items', []),
            pods_owner_kind,
            kind_top_level,
            obj_name)

        valid_replica_set = self.valid_replica_set(owned_rep_sets)

        if len(valid_replica_set) < 1:
            log.error(f'Failed to find {pods_owner_kind} owned by '
                      f'{kind_top_level}/{obj_name}.')
            return []
        if len(valid_replica_set) > 1:
            msg = f'There can only be single {pods_owner_kind}. ' \
                  f'Found: {json.dumps(valid_replica_set)}'
            log.error(msg)
            raise Exception(msg)
        pods_owner_name = valid_replica_set[0]['metadata']['name']
        # Find Pods owned by the ReplicaSet.
        all_pods = self._exec_stdout_json(['get', 'pods',
                                           '-o', 'json',
                                           '--namespace', namespace])
        return self._filter_objects_owned(all_pods['items'], 'Pod',
                                          pods_owner_kind, pods_owner_name)

    @should_connect
    def _get_pods_regular(self, namespace, owner_kind, owner_name):
        kind = 'Pod'
        all_pods = self._exec_stdout_json(['get', kind,
                                           '-o', 'json',
                                           '--namespace', namespace])
        if len(all_pods) < 1:
            log.warning(f'No {kind} in namespace {namespace}.')
            return []
        return self._filter_objects_owned(all_pods['items'], kind,
                                          owner_kind, owner_name)

    def _get_pods(self, namespace, obj_kind, obj_name) -> list:
        if 'Deployment' == obj_kind:
            return self._get_pods_deployment(namespace, obj_name)

        if 'CronJob' == obj_kind:
            return self._get_pods_cronjob(namespace, obj_name)

        if obj_kind in ['Job', 'DaemonSet', 'StatefulSet']:
            return self._get_pods_regular(namespace, obj_kind, obj_name)

    def _get_component_logs(self,
                            namespace: str,
                            obj_kind: str,
                            obj_name: str,
                            since: datetime,
                            num_lines: int) -> str:
        """
        Given Kubernetes workload object kind `obj_kind` and name `obj_name`
        running in `namespace`, returns max `num_lines` logs from `since` of all
        containers running in all its pods.

        :param namespace: str - namespace component is running in
        :param obj_kind: str - K8s object kind (e.g. Deployment, Job, etc.)
        :param obj_name: str - K8s object name (e.g. nginx)
        :param since: datetime - from what time to collect the logs
        :param num_lines: int - max number of log lines to collect
        :return: str - logs as string
        """
        pods = self._get_pods(namespace, obj_kind, obj_name)
        try:
            return self._get_pods_logs(namespace, pods, since, num_lines)
        except Exception as ex:
            log.error('Problem getting logs string: %s ', ex)
        return ''

    WORKLOAD_OBJECT_KINDS = \
        ['Deployment',
         'Job',
         'CronJob',
         'StatefulSet',
         'DaemonSet',
         'Pod']

    @should_connect
    def log(self, component: str, since: datetime, num_lines: int,
            namespace: str = None) -> str:
        """
        Given `component` as `<K8s workload object kind>/<name>` (e.g. Deployment/nginx),
        returns logs of all the containers of all the pods belonging to the
        `component` (as sting).

        Only Kubernetes workload object kinds (which actually can contain Pods)
        are considered for collection of logs.

        :param component: str - `<K8s object kind>/<name>` (e.g. Deployment/nginx)
        :param since: datetime - from what time to collect the logs
        :param num_lines: int - max number of log lines to collect
        :param namespace:
        :return: str - logs as string
        """

        if "/" in component:
            obj_kind, obj_name = component.split('/', 1)
            if obj_kind not in self.WORKLOAD_OBJECT_KINDS:
                msg = f"There are no meaningful logs for '{obj_kind}'."
                log.warning(msg)
                return f'{self._timestamp_now_utc()} {msg}\n'
        else:
            obj_kind = "Deployment"
            obj_name = component

        if not namespace:
            namespace = self.namespace

        log.info(f'Getting Kubernetes logs for: Object kind {obj_kind} '
                 f'Object name {obj_name} in namespace {namespace}')

        try:
            return self._get_component_logs(namespace, obj_kind,
                                            obj_name, since, num_lines)
        except Exception as ex:
            msg = f'There was an error getting logs for: {component}'
            log.error('%s: %s', msg, ex)
            return f'{self._timestamp_now_utc()} {msg}\n'

    @staticmethod
    def _extract_object_info(kube_resource):
        resource_kind = kube_resource['kind']
        node_id = '.'.join([resource_kind,
                            kube_resource['metadata']['name']])
        object_info = {'node-id': node_id}
        if resource_kind == 'Deployment':
            Kubernetes._object_info_deployment(kube_resource, object_info)
        if resource_kind == 'Service':
            Kubernetes._object_info_service(kube_resource, object_info)
        return object_info

    @staticmethod
    def _object_info_service(kube_resource, object_info):
        ports = kube_resource['spec']['ports']
        for port in ports:
            external_port = port.get('nodePort')
            if external_port:
                internal_port = port['port']
                protocol = port['protocol'].lower()
                object_info[f'{protocol}.{internal_port}'] = str(external_port)

    @staticmethod
    def _object_info_deployment(kube_resource, object_info):
        replicas_desired = kube_resource['spec']['replicas']
        replicas_running = kube_resource['status'].get('readyReplicas', 0)
        object_info['replicas.desired'] = str(replicas_desired)
        object_info['replicas.running'] = str(replicas_running)

    @should_connect
    def _get_objects_in_namespace(self, object_kinds: List[str],
                                  namespace: str) -> list:
        objects = ','.join(object_kinds)
        cmd = self.build_cmd_line(
            ['get', objects, '--namespace', namespace, '-o', 'json'])
        return json.loads(execute_cmd(cmd).stdout).get('items', [])

    @should_connect
    def _get_objects_by_deployment_uuid(self, deployment_uuid: str,
                                        object_kinds: List[str] = None) -> list:
        objects = ','.join(object_kinds)
        cmd = self.build_cmd_line(
            ['get', objects, '--all-namespaces', '-o', 'json',
             '-l', f'nuvla.deployment.uuid={deployment_uuid}'])
        kube_objects = json.loads(execute_cmd(cmd).stdout).get('items', [])

        return [self._extract_object_info(kube_resource)
                for kube_resource in kube_objects]

    DEFAULT_OBJECTS = ['deployments', 'services']

    @should_connect
    def get_objects(self, deployment_uuid, object_kinds: List[str]):

        object_kinds = object_kinds or self.DEFAULT_OBJECTS

        objects = self._get_objects_by_deployment_uuid(deployment_uuid,
                                                       object_kinds)
        if objects:
            log.debug('Found objects %s by deployment UUID label %s',
                      objects, deployment_uuid)
            return objects

        log.warning(f'No objects found by deployment UUID label: {deployment_uuid}')

        namespace = deployment_uuid

        kube_objects = self._get_objects_in_namespace(object_kinds, namespace)
        objects = [self._extract_object_info(kube_resource)
                   for kube_resource in kube_objects]
        if not objects:
            log.warning(f'No objects found in namespace: {namespace}')
        else:
            log.debug('Found objects %s in namespace %s',
                      objects, deployment_uuid)
        return objects

    @should_connect
    def version(self) -> dict:
        cmd = self.build_cmd_line(['version', '-o', 'json'])
        version = execute_cmd(cmd, timeout=5).stdout
        return json.loads(version)

    @staticmethod
    def _get_namespace_local():
        cmd = ['cat', '/var/run/secrets/kubernetes.io/serviceaccount/namespace']
        return execute_cmd(cmd).stdout.strip()

    @property
    def namespace(self):
        """
        Returns namespace current container is running in.
        """
        if self._namespace is None:
            self._namespace = self._get_namespace_local()
        return self._namespace

    def _wait_workload_succeeded(self, workload_name, namespace: str, timeout_min=5):
        """
        Check that a workload `workload_name` has completed.
        Runs until the success criteria is met.

        workload_name: the name of the workload object kind in Kubernetes.
        """

        # FIXME: If workload didn't succed, we should raise an exception and
        #  provide the logs of the application.

        t_end = time.time() + 60 * timeout_min

        cmd = self.build_cmd_line(['-n', namespace,
                                   'get', workload_name, '-o', 'json'])
        while time.time() < t_end:
            try:
                cmd_result = execute_cmd(cmd)
            except Exception as ex:
                log.error('Failed to execute %s: %s', cmd, ex)
                return
            status = json.loads(cmd_result.stdout).get('status', {})
            log.debug('Workload %s status: %s', workload_name, status)

            succeeded = status.get('succeeded', 0)
            if succeeded == 1:
                return
            time.sleep(1)
        return True

    @should_connect
    def wait_job_succeeded(self, job_name, namespace, timeout_min=5):
        """
        Check that a job `job_name` has completed.
        Runs until the success criteria is met.

        job_name: the name of the Job in kubernetes
        """
        self._wait_workload_succeeded(self.K8S_JOB + job_name,
                                      namespace,
                                      timeout_min)
