# -*- coding: utf-8 -*-
import os
import json
import yaml
import base64
import logging
import datetime
from tempfile import TemporaryDirectory
from .utils import execute_cmd, join_stderr_stdout, create_tmp_file, \
    generate_registry_config, extract_host_from_url
from .connector import Connector, should_connect

log = logging.getLogger('kubernetes')


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
    def _create_deployment_context(directory_path, stack_name, docker_compose,
                                   files, registries_auth):
        manifest_file_path = directory_path + '/manifest.yml'
        with open(manifest_file_path, 'w') as manifest_file:
            manifest_file.write(docker_compose)

        namespace_file_path = directory_path + '/namespace.yml'
        with open(namespace_file_path, 'w') as namespace_file:
            namespace_data = {'apiVersion': 'v1',
                              'kind': 'Namespace',
                              'metadata': {'name': stack_name}}
            yaml.safe_dump(namespace_data, namespace_file, allow_unicode=True)

        kustomization_data = {'namespace': stack_name,
                              'resources': ['manifest.yml', 'namespace.yml']}

        if files:
            for file_info in files:
                file_path = directory_path + "/" + file_info['file-name']
                file = open(file_path, 'w')
                file.write(file_info['file-content'])
                file.close()

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
        docker_compose = kwargs['docker_compose']
        envsubst_shell_format = ' '.join(['${}'.format(k) for k in env.keys()])
        docker_compose_env_subs = execute_cmd(
            ['envsubst', envsubst_shell_format],
            env=env, input=docker_compose).stdout
        registries_auth = kwargs['registries_auth']
        stack_name = kwargs['stack_name']
        files = kwargs['files']

        with TemporaryDirectory() as tmp_dir_name:
            Kubernetes._create_deployment_context(
                tmp_dir_name, stack_name, docker_compose_env_subs, files,
                registries_auth)

            cmd_deploy = self.build_cmd_line(['apply', '-k', tmp_dir_name])

            result = join_stderr_stdout(execute_cmd(cmd_deploy))

            services = self._stack_services(stack_name)

            return result, services

    update = start

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        # docker_compose = kwargs['docker_compose']
        stack_name = kwargs['stack_name']
        # files = kwargs['files']
        #
        # with TemporaryDirectory() as tmp_dir_name:
        #     KubernetesCliConnector._create_deployment_context(tmp_dir_name, stack_name,
        #                                                       docker_compose, files)
        # cmd_stop = self.build_cmd_line(['delete', '-k', tmp_dir_name])
        cmd_stop = self.build_cmd_line(['delete', 'namespace', stack_name])

        try:
            return join_stderr_stdout(execute_cmd(cmd_stop))
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                return 'namespace "{}" already stopped (not found)'.format(
                    stack_name)
            else:
                raise ex

    @should_connect
    def list(self, filters=None):
        # cmd = self.build_cmd_line(['stack', 'ls'])
        # return execute_cmd(cmd)
        pass

    @should_connect
    def log(self, component: str, since: datetime, lines: int,
            **kwargs) -> str:
        namespace = kwargs['namespace']
        since_opt = ['--since-time', since.isoformat()] if since else []
        list_opts = [component, '--timestamps=true', '--tail', str(lines),
                     '--namespace', namespace] + since_opt
        cmd = self.build_cmd_line(['logs'] + list_opts)
        return execute_cmd(cmd).stdout

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

    def _stack_services(self, stack_name):
        cmd_services = self.build_cmd_line(['get', 'services', '--namespace',
                                            stack_name, '-o', 'json'])
        kube_services = json.loads(execute_cmd(cmd_services).stdout).get(
            'items', [])

        cmd_deployments = self.build_cmd_line(
            ['get', 'deployments', '--namespace',
             stack_name, '-o', 'json'])
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
    def stack_services(self, stack_name):
        return self._stack_services(stack_name)

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        return extract_host_from_url(self.endpoint)

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass

from ..job import Job
class K8sEdgeMgmt(Kubernetes):
    '''Here'''
    def __init__(self, job):

        # if not job.is_in_pull_mode():
            # raise ValueError('This action is only supported by pull mode')

        # FIXME: need to be parametrised.
        path = '/srv/nuvlaedge/shared'
        super(K8sEdgeMgmt, self).__init__(ca=open(f'{path}/ca.pem',encoding="utf8").read(),
                                          key=open(f'{path}/key.pem',encoding="utf8").read(),
                                          cert=open(f'{path}/cert.pem',encoding="utf8").read(),
                                          endpoint=get_kubernetes_local_endpoint())
        # log.info('Where does this logging message land?')

    @should_connect
    def reboot(self):

        log.info('We have CA file %s ', self.ca)
        log.info('We have certificate file %s ', self.cert)
        log.info('We have key file %s ', self.key)
        log.info('We have endpoint %s ', self.endpoint)

        reboot_yaml_manifest = """
        apiVersion: batch/v1
        kind: Job
        metadata:
          name: reboot
        spec:
          template:
            spec:
              containers:
              - name: reboot
                image: busybox
                command: ['sh', '-c', 'echo s > /sysrq']
                volumeMounts:
                - name: reboot-vol
                  mountPath: /sysrq
              volumes:
              - name: reboot-vol
                hostPath:
                  path: /proc/sysrq-trigger
              restartPolicy: Never
          backoffLimit: 4

        """
        with TemporaryDirectory() as tmp_dir_name:
            with open(tmp_dir_name + '/reboot_job_manifest.yaml', 'w',encoding="utf-8") as reboot_manifest_file:
                reboot_manifest_file.write(reboot_yaml_manifest)
            cmd_reboot = \
                self.build_cmd_line(['apply', '-f', tmp_dir_name + '/reboot_job_manifest.yaml'])
            reboot_result = join_stderr_stdout(execute_cmd(cmd_reboot))
            log.info('Result of the reboot ... does not really make sense... %s',reboot_result)
