# -*- coding: utf-8 -*-
import logging
import os
import re
import json
import yaml
from subprocess import run, PIPE, STDOUT
from tempfile import NamedTemporaryFile, TemporaryDirectory

from .connector import Connector, should_connect

log = logging.getLogger('kubernetes_cli_connector')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return KubernetesCliConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                                  key=api_credential.get('key').replace("\\n", "\n"),
                                  endpoint=api_infrastructure_service.get('endpoint'))


def append_os_env(env):
    final_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if value:
                final_env[key] = value
    return final_env


def execute_cmd(cmd, **kwargs):
    env = append_os_env(kwargs.get('env'))
    result = run(cmd, stdout=PIPE, stderr=STDOUT, env=env)
    if result.returncode == 0:
        return result.stdout.decode('UTF-8')
    else:
        raise Exception(result.stdout.decode('UTF-8'))


class KubernetesCliConnector(Connector):

    def __init__(self, **kwargs):
        super(KubernetesCliConnector, self).__init__(**kwargs)

        # Mandatory kwargs
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']

        self.endpoint = self.kwargs['endpoint']
        self.cert_key_file = None

    @property
    def connector_type(self):
        return 'Kubernetes-cli'

    def connect(self):
        log.info('Connecting to endpoint {}'.format(self.endpoint))
        auth_file = NamedTemporaryFile(delete=True)
        auth_text = self.cert + '\n' + self.key
        auth_file.write(auth_text.encode())
        auth_file.flush()
        self.cert_key_file = auth_file
        return auth_file

    def clear_connection(self, connect_result):
        if connect_result:
            connect_result.close()

    def build_cmd_line(self, list_cmd):
        return ['kubectl', '-s', self.endpoint, '--client-certificate', self.cert_key_file.name,
                '--client-key', self.cert_key_file.name, '--insecure-skip-tls-verify=true'] \
               + list_cmd

    @staticmethod
    def _create_deployment_context(directory_path, stack_name, docker_compose, files):
        manifest_file_path = directory_path + '/manifest.yml'
        with open(manifest_file_path, 'w') as manifest_file:
            manifest_file.write(docker_compose)

        namespace_file_path = directory_path + '/namespace.yml'
        with open(namespace_file_path, 'w') as namespace_file:
            namespace_data = {'apiVersion': 'v1',
                              'kind': 'Namespace',
                              'metadata': {'name': stack_name}}
            yaml.safe_dump(namespace_data, namespace_file, allow_unicode=True)

        kustomization_file_path = directory_path + '/kustomization.yml'
        with open(kustomization_file_path, 'w') as kustomization_file:
            kustomization_data = {'namespace': stack_name,
                                  'resources': ['manifest.yml', 'namespace.yml']}
            yaml.safe_dump(kustomization_data, kustomization_file, allow_unicode=True)

        if files:
            for file_info in files:
                file_path = directory_path + "/" + file_info['file-name']
                file = open(file_path, 'w')
                file.write(file_info['file-content'])
                file.close()

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        docker_compose = kwargs['docker_compose']
        stack_name = kwargs['stack_name']
        env = kwargs['env']
        files = kwargs['files']

        with TemporaryDirectory() as tmp_dir_name:
            KubernetesCliConnector._create_deployment_context(tmp_dir_name, stack_name,
                                                              docker_compose, files)
            cmd_deploy = self.build_cmd_line(['apply', '-k', tmp_dir_name])

            result = execute_cmd(cmd_deploy, env=env)

            services = self._stack_services(stack_name)

            return result, services

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
            return execute_cmd(cmd_stop)
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                return 'namespace "{}" already stopped (not found)'.format(stack_name)
            else:
                raise ex

    @should_connect
    def update(self, service_name, **kwargs):
        pass

    @should_connect
    def list(self, filters=None):
        # cmd = self.build_cmd_line(['stack', 'ls'])
        # return execute_cmd(cmd)
        pass

    @should_connect
    def log(self, list_opts):
        cmd = self.build_cmd_line(['logs'] + list_opts)
        return execute_cmd(cmd)

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
                    service_info['{}.{}'.format(protocol, internal_port)] = str(external_port)
        return service_info

    def _stack_services(self, stack_name):
        cmd_services = self.build_cmd_line(['get', 'services', '--namespace',
                                            stack_name, '-o', 'json'])
        kube_services = json.loads(execute_cmd(cmd_services)).get('items', [])

        cmd_deployments = self.build_cmd_line(['get', 'deployments', '--namespace',
                                               stack_name, '-o', 'json'])
        kube_deployments = json.loads(execute_cmd(cmd_deployments)).get('items', [])

        services = [KubernetesCliConnector._extract_service_info(kube_resource)
                    for kube_resource in kube_services + kube_deployments]

        return services

    @should_connect
    def stack_services(self, stack_name):
        return self._stack_services(stack_name)

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', self.endpoint).group('host')

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass
