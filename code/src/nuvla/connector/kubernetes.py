# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
import yaml

from datetime import datetime
from tempfile import TemporaryDirectory

from ..job.job import Job
from .connector import Connector, should_connect
from .utils import (create_tmp_file,
                    execute_cmd,
                    generate_registry_config,
                    join_stderr_stdout)

log = logging.getLogger('kubernetes')


class OperationNotAllowed(Exception):
    pass


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return Kubernetes(
        ca=api_credential.get('ca', '').replace("\\n", "\n"),
        cert=api_credential.get('cert', '').replace("\\n", "\n"),
        key=api_credential.get('key', '').replace("\\n", "\n"),
        endpoint=api_infrastructure_service.get('endpoint'))


def get_kubernetes_local_endpoint():
    kubernetes_host = os.getenv('KUBERNETES_SERVICE_HOST')
    kubernetes_port = os.getenv('KUBERNETES_SERVICE_PORT')
    if kubernetes_host and kubernetes_port:
        return f'https://{kubernetes_host}:{kubernetes_port}'
    return ''


class Kubernetes(Connector):

    def __init__(self, **kwargs):
        super(Kubernetes, self).__init__(**kwargs)

        # Mandatory kwargs
        self.ca = self.kwargs['ca']
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']

        self.endpoint = self.kwargs['endpoint']
        self.ca_file = None
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'Kubernetes-cli'

    def connect(self):
        log.info('Connecting to endpoint {}'.format(self.endpoint))
        self.ca_file = create_tmp_file(self.ca)
        self.cert_file = create_tmp_file(self.cert)
        self.key_file = create_tmp_file(self.key)

    def clear_connection(self, connect_result):
        if self.ca_file:
            self.ca_file.close()
            self.ca_file = None
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def build_cmd_line(self, list_cmd):
        return ['kubectl', '-s', self.endpoint,
                '--client-certificate', self.cert_file.name,
                '--client-key', self.key_file.name,
                '--certificate-authority', self.ca_file.name] \
               + list_cmd

    @staticmethod
    def _create_deployment_context(directory_path, namespace, docker_compose,
                                   files, registries_auth):
        manifest_file_path = directory_path + '/manifest.yml'
        with open(manifest_file_path, 'w') as manifest_file:
            manifest_file.write(docker_compose)

        namespace_file_path = directory_path + '/namespace.yml'
        with open(namespace_file_path, 'w') as namespace_file:
            namespace_data = {'apiVersion': 'v1',
                              'kind': 'Namespace',
                              'metadata': {'name': namespace}}
            yaml.safe_dump(namespace_data, namespace_file, allow_unicode=True)

        kustomization_data = {'namespace': namespace,
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

        kustomization_file_path = directory_path + '/kustomization.yml'
        with open(kustomization_file_path, 'w') as kustomization_file:
            yaml.safe_dump(kustomization_data, kustomization_file,
                           allow_unicode=True)

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        env = kwargs['env']
        files = kwargs['files']
        manifest = kwargs['docker_compose']
        namespace = kwargs['name']
        registries_auth = kwargs['registries_auth']

        envsubst_shell_format = ' '.join(['${}'.format(k) for k in env.keys()])
        cmd = ['envsubst', envsubst_shell_format]
        manifest_env_subs = execute_cmd(cmd,
                                        env=env,
                                        input=manifest).stdout

        with TemporaryDirectory() as tmp_dir_name:
            Kubernetes._create_deployment_context(tmp_dir_name,
                                                  namespace,
                                                  manifest_env_subs,
                                                  files,
                                                  registries_auth)

            cmd_deploy = self.build_cmd_line(['apply', '-k', tmp_dir_name])

            result = join_stderr_stdout(execute_cmd(cmd_deploy))

            services = self._get_services(namespace)

            return result, services

    update = start

    @should_connect
    def stop(self, **kwargs):
        namespace = kwargs['name']

        cmd_stop = self.build_cmd_line(['delete', 'namespace', namespace])

        try:
            return join_stderr_stdout(execute_cmd(cmd_stop))
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                return f'Namespace "{namespace}" not found.'
            else:
                raise ex

    @should_connect
    def list(self, filters=None):
        # FIXME: Implement.
        # cmd = self.build_cmd_line(['stack', 'ls'])
        # return execute_cmd(cmd)
        pass

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
        component_pods = []
        for obj in objects:
            if obj['kind'] == kind and 'ownerReferences' in obj['metadata']:
                owner = obj['metadata']['ownerReferences'][0]
                if owner_kind == owner['kind'] and owner_name == owner['name']:
                    component_pods.append(obj)
        return component_pods

    def _exec_stdout_json(self, cmd_params) -> {}:
        cmd = self.build_cmd_line(cmd_params)
        cmd_stdout = execute_cmd(cmd).stdout
        return json.loads(cmd_stdout)

    @should_connect
    def _get_pods_cronjob(self, namespace, obj_name) -> list:
        # Find Jobs associated with the CronJob and get its name.
        kind_top_level = 'CronJob'
        pods_owner_kind = 'Job'
        jobs = self._exec_stdout_json(['get', pods_owner_kind,
                                       '-o', 'json',
                                       '--namespace', namespace])
        jobs_owned_by_cronjob = self._filter_objects_owned(jobs.get('items', []),
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
                                             'Pod', pods_owner_kind, pods_owner_name)
            pods.extend(res)
        return pods

    @should_connect
    def _get_pods_deployment(self, namespace, obj_name) -> list:
        # Find ReplicaSet associated with the Deployment and get its name.
        kind_top_level = 'Deployment'
        pods_owner_kind = 'ReplicaSet'
        replicasets = self._exec_stdout_json(['get', pods_owner_kind,
                                              '-o', 'json',
                                              '--namespace', namespace])
        kinds_second_level = self._filter_objects_owned(
            replicasets.get('items', []),
            pods_owner_kind,
            kind_top_level,
            obj_name)
        if len(kinds_second_level) < 1:
            log.error(f'Failed to find {pods_owner_kind} owned by '
                      f'{kind_top_level}/{obj_name}.')
            return []
        if len(kinds_second_level) > 1:
            msg = f'There can only be single {pods_owner_kind}. ' \
                  f'Found: {kinds_second_level}'
            log.error(msg)
            raise Exception(msg)
        pods_owner_name = kinds_second_level[0]['metadata']['name']
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
         'DaemonSet']

    @should_connect
    def log(self, component: str, since: datetime, num_lines: int, **kwargs) -> str:
        """
        Given `component` as `<K8s object kind>/<name>` (e.g. Deployment/nginx),
        returns logs of all the containers of all the pods belonging to the
        `component` (as sting).

        Only Kubernetes workload object kinds (which actually can contain Pods)
        are considered for collection of logs.

        :param component: str - `<K8s object kind>/<name>` (e.g. Deployment/nginx)
        :param since: datetime - from what time to collect the logs
        :param num_lines: int - max number of log lines to collect
        :param kwargs: optional parameters
        :return: str - logs as string
        """

        obj_kind, obj_name = component.split('/')
        if obj_kind not in self.WORKLOAD_OBJECT_KINDS:
            msg = f"There are no meaningful logs for '{obj_kind}'."
            log.warning(msg)
            return f'{self._timestamp_now_utc()} {msg}\n'

        try:
            log.info('Getting logs for: %s', component)
            return self._get_component_logs(kwargs['namespace'], obj_kind,
                                            obj_name, since, num_lines)
        except Exception as ex:
            msg = f'There was an error getting logs for: {component}'
            log.error('%s: %s', msg, ex)
            return f'{self._timestamp_now_utc()} {msg}\n'

    @staticmethod
    def _extract_service_info(kube_resource):
        resource_kind = kube_resource['kind']
        node_id = '.'.join([resource_kind,
                            kube_resource['metadata']['name']])
        service_info = {'node-id': node_id}
        if resource_kind == 'Deployment':
            replicas_desired = kube_resource['spec']['replicas']
            replicas_running = kube_resource['status'].get('readyReplicas', 0)
            service_info['replicas.desired'] = str(replicas_desired)
            service_info['replicas.running'] = str(replicas_running)
        if resource_kind == 'Service':
            ports = kube_resource['spec']['ports']
            for port in ports:
                external_port = port.get('nodePort')
                if external_port:
                    internal_port = port['port']
                    protocol = port['protocol'].lower()
                    service_info[f'{protocol}.{internal_port}'] = str(
                        external_port)
        return service_info

    def _get_services(self, namespace):
        cmd_services = self.build_cmd_line(['get', 'services', '--namespace',
                                            namespace, '-o', 'json'])
        kube_services = json.loads(execute_cmd(cmd_services).stdout).get(
            'items', [])

        cmd_deployments = self.build_cmd_line(
            ['get', 'deployments', '--namespace',
             namespace, '-o', 'json'])
        kube_deployments = json.loads(execute_cmd(cmd_deployments).stdout).get(
            'items', [])

        services = [Kubernetes._extract_service_info(kube_resource)
                    for kube_resource in kube_services + kube_deployments]

        return services

    @should_connect
    def version(self):
        cmd = self.build_cmd_line(['version', '-o', 'json'])
        version = execute_cmd(cmd, timeout=5).stdout
        return json.loads(version)

    @should_connect
    def get_services(self, name, env, **kwargs):
        return self._get_services(name)

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        return extract_host_from_url(self.endpoint)

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass


class K8sEdgeMgmt(Kubernetes):
    def __init__(self, job: Job):

        if not job.is_in_pull_mode:
            raise OperationNotAllowed(
                'NuvlaEdge management actions are only supported in pull mode.')

        # FIXME: This needs to be parametrised.
        path = '/srv/nuvlaedge/shared'
        super(K8sEdgeMgmt, self).__init__(
            ca=open(f'{path}/ca.pem', encoding="utf8").read(),
            key=open(f'{path}/key.pem', encoding="utf8").read(),
            cert=open(f'{path}/cert.pem', encoding="utf8").read(),
            endpoint=get_kubernetes_local_endpoint())

    @should_connect
    def reboot(self):
        reboot_yaml_manifest = """
apiVersion: batch/v1
kind: Job
metadata:
  name: reboot
spec:
  ttlSecondsAfterFinished: 0
  template:
    spec:
      containers:
      - name: reboot
        image: busybox
        command: ['sh', '-c', 'sleep 10 && echo b > /sysrq']
        volumeMounts:
        - name: reboot-vol
          mountPath: /sysrq
      volumes:
      - name: reboot-vol   
        hostPath:
          path: /proc/sysrq-trigger
      restartPolicy: Never
  backoffLimit: 0
"""
        with TemporaryDirectory() as tmp_dir_name:

            fpath = os.path.join(tmp_dir_name, 'reboot_job_manifest.yaml')
            with open(fpath, 'w', encoding="utf-8") as fh:
                fh.write(reboot_yaml_manifest)

            cmd_reboot = self.build_cmd_line(['apply', '-f', fpath])
            output = join_stderr_stdout(execute_cmd(cmd_reboot))

            log.debug('Output from reboot Job: %s', output)
