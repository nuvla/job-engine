# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime
from tempfile import TemporaryDirectory
from .utils import (create_tmp_file,
                    execute_cmd,
                    generate_registry_config,
                    join_stderr_stdout,
                    LOCAL)
from .connector import Connector, should_connect

log = logging.getLogger('docker_stack')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerStack(
        cert=api_credential.get('cert').replace("\\n", "\n"),
        key=api_credential.get('key').replace("\\n", "\n"),
        endpoint=api_infrastructure_service.get('endpoint'))


class DockerStack(Connector):

    def __init__(self, **kwargs):
        super(DockerStack, self).__init__(**kwargs)

        # Mandatory kwargs
        self.cert = kwargs.get('cert')
        self.key = kwargs.get('key')
        self.endpoint = (kwargs.get('endpoint', '') or LOCAL).replace('https://', '')
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'Docker-cli'

    def connect(self):
        log.info('Connecting to endpoint {}'.format(self.endpoint))
        self.cert_file = create_tmp_file(self.cert)
        self.key_file = create_tmp_file(self.key)

    def clear_connection(self, connect_result):
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def build_cmd_line(self, list_cmd):
        if self.endpoint == LOCAL:
            remote_tls = []
        else:
            remote_tls = ['-H', self.endpoint, '--tls',
                          '--tlscert', self.cert_file.name,
                          '--tlskey', self.key_file.name,
                          '--tlscacert', self.cert_file.name]
        return ['docker'] + remote_tls + list_cmd

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        docker_compose = kwargs['docker_compose']
        stack_name = kwargs['name']
        env = kwargs['env']
        files = kwargs['files']
        registries_auth = kwargs['registries_auth']

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

            if registries_auth:
                config_path = tmp_dir_name + "/config.json"
                config = open(config_path, 'w')
                config.write(generate_registry_config(registries_auth))
                config.close()

            cmd_deploy = self.build_cmd_line(
                ['--config', tmp_dir_name, 'stack', 'deploy',
                 '--with-registry-auth', '--prune', '-c', compose_file_path,
                 stack_name])

            result = join_stderr_stdout(execute_cmd(cmd_deploy, env=env))

            services = self._stack_services(stack_name)

            return result, services

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        stack_name = kwargs['name']

        cmd = self.build_cmd_line(['stack', 'rm', stack_name])
        return join_stderr_stdout(execute_cmd(cmd))

    update = start

    @should_connect
    def list(self, filters=None):
        cmd = self.build_cmd_line(['stack', 'ls'])
        return execute_cmd(cmd).stdout

    @should_connect
    def log(self, component: str, since: datetime, lines: int,
            **_kwargs) -> str:
        since_opt = ['--since', since.isoformat()] if since else []
        list_opts = ['-t', '--no-trunc', '--tail', str(lines)] + since_opt + [
            component]
        cmd = self.build_cmd_line(['service', 'logs'] + list_opts)
        return execute_cmd(cmd, sterr_in_stdout=True).stdout

    @staticmethod
    def ports_info(port):
        external_port_info, internal_port_info = port.split('->')
        external_port = external_port_info.split(':')[1]
        internal_port, protocol = internal_port_info.split('/')
        return protocol, internal_port, external_port

    def resolve_task_host_ip(self, task_id):
        json_task = json.loads(
            execute_cmd(self.build_cmd_line(['inspect', task_id])).stdout)
        node_id = json_task[0]['NodeID'] if len(json_task) > 0 else None
        if node_id:
            json_node = json.loads(execute_cmd(
                self.build_cmd_line(['node', 'inspect', node_id])).stdout)
            return json_node[0].get('Status', {}).get('Addr') if len(
                json_node) > 0 else ''
        return ''

    def _extract_service_info(self, stack_name, service):
        service_info = {}
        service_json = json.loads(service)
        service_id = service_json['ID']
        service_info['image'] = service_json['Image']
        service_info['mode'] = service_json['Mode']
        service_info['service-id'] = service_id
        node_id = service_json['Name'][len(stack_name) + 1:]
        service_info['node-id'] = node_id
        replicas = service_json['Replicas'].split('/')
        replicas_desired = replicas[1]
        replicas_running = replicas[0]
        service_info['replicas.desired'] = replicas_desired
        service_info['replicas.running'] = replicas_running
        ports = filter(None, service_json['Ports'].split(','))
        for port in ports:
            protocol, internal_port, external_port = DockerStack.ports_info(
                port)
            service_info[
                '{}.{}'.format(protocol, internal_port)] = external_port

        # Check if service has host ports published
        cmd = self.build_cmd_line(
            ['service', 'ps', '--filter', 'desired-state=running',
             '--format', '{{ json . }}', service_id])
        tasks = [json.loads(task_line) for task_line in
                 execute_cmd(cmd).stdout.splitlines()]
        for task_json in tasks:
            task_ports = filter(None, task_json['Ports'].split(','))
            task_id = task_json['ID']
            task_replica_number = task_json['Name'].split('.')[-1]
            for task_port in task_ports:
                task_protocol, task_internal_port, task_external_port = \
                    DockerStack.ports_info(task_port)
                host_ip = self.resolve_task_host_ip(task_id)
                service_info['{}.{}.{}'.format(
                    task_replica_number, task_protocol, task_internal_port)] = \
                    '{}:{}'.format(host_ip, task_external_port)
        return service_info

    def _stack_services(self, stack_name):
        cmd = self.build_cmd_line(['stack', 'services', '--format',
                                   '{{ json . }}', stack_name])
        services = [self._extract_service_info(stack_name, service)
                    for service in execute_cmd(cmd).stdout.splitlines()]
        return services

    @should_connect
    def get_services(self, name, env, **kwargs):
        return self._stack_services(name)

    @should_connect
    def info(self):
        cmd = self.build_cmd_line(['info', '--format', '{{ json . }}'])
        info = json.loads(execute_cmd(cmd, timeout=5).stdout)
        server_errors = info.get('ServerErrors', [])
        if len(server_errors) > 0:
            raise Exception(server_errors[0])
        return info

    @staticmethod
    def registry_login(**kwargs):
        # Mandatory kwargs
        username = kwargs['username']
        password = kwargs['password']
        serveraddress = kwargs['serveraddress']

        with TemporaryDirectory() as tmp_dir_name:
            config_path = tmp_dir_name + "/config.json"
            config = open(config_path, 'w')
            json.dump({'auths': {'': {}}}, config)
            config.close()
            cmd_login = ['docker', '--config', tmp_dir_name, 'login',
                         '--username', username, '--password-stdin',
                         'https://' + serveraddress.replace('https://', '')]
            return execute_cmd(cmd_login, input=password).stdout
