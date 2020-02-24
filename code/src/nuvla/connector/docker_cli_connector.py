# -*- coding: utf-8 -*-
import re
import json
import logging
from tempfile import TemporaryDirectory
from .utils import execute_cmd, create_tmp_file
from .connector import Connector, should_connect

log = logging.getLogger('docker_cli_connector')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerCliConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                              key=api_credential.get('key').replace("\\n", "\n"),
                              endpoint=api_infrastructure_service.get('endpoint'))


class DockerCliConnector(Connector):

    def __init__(self, **kwargs):
        super(DockerCliConnector, self).__init__(**kwargs)

        # Mandatory kwargs
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']
        self.endpoint = self.kwargs['endpoint'].replace('https://', '')
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
        return ['docker', '-H', self.endpoint, '--tls', '--tlscert', self.cert_file.name,
                '--tlskey', self.key_file.name, '--tlscacert', self.cert_file.name] \
               + list_cmd

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        docker_compose = kwargs['docker_compose']
        stack_name = kwargs['stack_name']
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
                json.dump({'auths': {'': {}}}, config)
                config.close()
                # we don't generate the config file to have an additional validation if login works
                for registry_auth in registries_auth:
                    cmd_login = self.build_cmd_line(
                        ['--config', tmp_dir_name, 'login',
                         '--username', registry_auth['username'], '--password-stdin',
                         'https://' + registry_auth['serveraddress']])
                    execute_cmd(cmd_login, input=registry_auth['password'])

            cmd_deploy = self.build_cmd_line(
                ['--config', tmp_dir_name, 'stack', 'deploy',
                 '--with-registry-auth', '-c', compose_file_path, stack_name])

            result = execute_cmd(cmd_deploy, env=env)

            services = self._stack_services(stack_name)

            return result, services

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        stack_name = kwargs['stack_name']

        cmd = self.build_cmd_line(['stack', 'rm', stack_name])
        return execute_cmd(cmd)

    update = start

    @should_connect
    def list(self, filters=None):
        cmd = self.build_cmd_line(['stack', 'ls'])
        return execute_cmd(cmd)

    @should_connect
    def log(self, list_opts):
        cmd = self.build_cmd_line(['service', 'logs'] + list_opts)
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
        stdout = execute_cmd(cmd)
        services = [DockerCliConnector._extract_service_info(stack_name, service)
                    for service in stdout.splitlines()]
        return services

    @should_connect
    def stack_services(self, stack_name):
        return self._stack_services(stack_name)

    @should_connect
    def info(self):
        cmd = self.build_cmd_line(['info', '--format', '{{ json . }}'])
        info = json.loads(execute_cmd(cmd, timeout=5))
        server_errors = info.get('ServerErrors', [])
        if len(server_errors) > 0:
            raise Exception(server_errors[0])
        return info

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', self.endpoint).group('host')

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass
