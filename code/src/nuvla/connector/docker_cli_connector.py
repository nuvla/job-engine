# -*- coding: utf-8 -*-
import logging
import os
import re
import json
from subprocess import run, PIPE, STDOUT
from tempfile import NamedTemporaryFile, TemporaryDirectory

from .connector import Connector, should_connect

log = logging.getLogger('docker_cli_connector')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerCliConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
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
        return result
    else:
        raise Exception(result.stdout.decode('UTF-8'))


class DockerCliConnector(Connector):

    def __init__(self, **kwargs):
        super(DockerCliConnector, self).__init__(**kwargs)

        # Mandatory kwargs
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']
        self.endpoint = self.kwargs['endpoint'].replace('https://', '')
        self.cert_key_file = None

    @property
    def connector_type(self):
        return 'Docker-cli'

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
        return ['docker', '-H', self.endpoint, '--tls', '--tlscert', self.cert_key_file.name,
                '--tlskey', self.cert_key_file.name] + list_cmd

    @should_connect
    def start(self, **kwargs):
        # Mandatory start_kwargs
        docker_compose = kwargs['docker_compose']
        stack_name = kwargs['stack_name']
        env = kwargs['env']
        files = kwargs['files']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            if files:
                for file_info in files:
                    file_path = tmp_dir_name + "/" + file_info['file-name']
                    file = open(file_path, 'w')
                    file.write(file_info['file-content'])
                    file.close()

            cmd_deploy = self.build_cmd_line(
                ['stack', 'deploy', '-c', compose_file_path, stack_name])

            result = execute_cmd(cmd_deploy, env=env)

            services = self._stack_services(stack_name)

            return result, services

    @should_connect
    def stop(self, ids):
        stack_name = ids[0]
        cmd = self.build_cmd_line(['stack', 'rm', stack_name])
        return execute_cmd(cmd)

    @should_connect
    def list(self, filters=None):
        cmd = self.build_cmd_line(['stack', 'ls'])
        return execute_cmd(cmd)

    @staticmethod
    def _extract_service_info(stack_name, service):
        service_info = {}
        service_json = json.loads(service)
        service_info['image'] = service_json['Image']
        service_info['mode'] = service_json['Mode']
        service_info['service-id'] = service_json['ID']
        node_id = service_json['Name'][len(stack_name) + 1:]
        service_info['node-id'] = node_id
        replicas = service_json['Replicas'].split('/')
        replicas_desired = replicas[1]
        replicas_running = replicas[0]
        service_info['replicas.desired'] = replicas_desired
        service_info['replicas.running'] = replicas_running
        ports = filter(None, service_json['Ports'].split(','))
        for port in ports:
            external_port_info, internal_port_info = port.split('->')
            external_port = external_port_info.split(':')[1]
            internal_port, protocol = internal_port_info.split('/')
            service_info['{}.{}'.format(protocol, internal_port)] = external_port
        return service_info

    def _stack_services(self, stack_name):
        cmd = self.build_cmd_line(['stack', 'services', '--format',
                                   '{{ json . }}', stack_name])
        stdout = execute_cmd(cmd).stdout.decode('UTF-8')
        services = [DockerCliConnector._extract_service_info(stack_name, service)
                    for service in stdout.splitlines()]
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
