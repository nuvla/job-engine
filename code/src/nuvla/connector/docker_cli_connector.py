# -*- coding: utf-8 -*-

from subprocess import run, PIPE, STDOUT
import logging
from tempfile import NamedTemporaryFile

from .connector import Connector, ConnectorError, should_connect

log = logging.getLogger('docker_cli_connector')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerCliConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                              key=api_credential.get('key').replace("\\n", "\n"),
                              endpoint=api_infrastructure_service.get('endpoint'))


def execute_cmd(cmd):
    result = run(cmd, stdout=PIPE, stderr=STDOUT)
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

        docker_base_cmd = ['docker', '-H', self.endpoint]

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
    def start(self, **start_kwargs):
        # Mandatory start_kwargs
        docker_compose = start_kwargs['docker_compose']
        stack_name = start_kwargs['stack_name']

        with NamedTemporaryFile() as compose_file:
            compose_file.write(docker_compose.encode())
            compose_file.flush()
            cmd = self.build_cmd_line(['stack', 'deploy', '-c', compose_file.name, stack_name])
            return execute_cmd(cmd)

    @should_connect
    def stop(self, ids):
        stack_name = ids[0]
        cmd = self.build_cmd_line(['stack', 'rm', stack_name])
        return execute_cmd(cmd)

    @should_connect
    def list(self, filters=None):
        cmd = self.build_cmd_line(['stack', 'ls'])
        return execute_cmd(cmd)

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, vm):
        pass

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass
