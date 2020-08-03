# -*- coding: utf-8 -*-
import re
import json
import logging
import yaml
from tempfile import TemporaryDirectory
from .utils import execute_cmd, create_tmp_file, generate_registry_config
from .connector import Connector, should_connect

log = logging.getLogger('docker_cli_connector')


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerComposeCliConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                              key=api_credential.get('key').replace("\\n", "\n"),
                              endpoint=api_infrastructure_service.get('endpoint'))


class DockerComposeCliConnector(Connector):

    def __init__(self, **kwargs):
        super(DockerComposeCliConnector, self).__init__(**kwargs)

        self.cert = self.kwargs.get('cert')
        self.key = self.kwargs.get('key')
        self.endpoint = self.kwargs.get('endpoint', '')
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'docker-compose-cli'

    def connect(self):
        log.info('Connecting to endpoint {}'.format(self.endpoint))
        if self.cert and self.key:
            self.cert_file = create_tmp_file(self.cert)
            self.key_file = create_tmp_file(self.key)

    def clear_connection(self, connect_result):
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def build_cmd_line(self, list_cmd, local=False, binary='docker-compose'):
        if local:
            remote_tls = []
        else:
            remote_tls = ['-H', self.endpoint, '--tls', '--tlscert', self.cert_file.name,
                          '--tlskey', self.key_file.name, '--tlscacert', self.cert_file.name]

        return [binary] + remote_tls + list_cmd

    def _execute_clean_command(self, cmd, **kwargs):
        try:
            return self.sanitize_command_output(execute_cmd(cmd, **kwargs))
        except Exception as e:
            error = self.sanitize_command_output(e.args[0])
            raise Exception(error)

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        docker_compose = kwargs['docker_compose']
        project_name = kwargs['stack_name']
        env = kwargs['env']
        registries_auth = kwargs['registries_auth']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            docker_config_prefix = []

            if registries_auth:
                config_path = tmp_dir_name + "/config.json"
                config = open(config_path, 'w')
                config.write(generate_registry_config(registries_auth))
                config.close()
                docker_config_prefix += ["export", "DOCKER_CONFIG=%s" % config_path, "&&"]

            cmd_deploy = docker_config_prefix + self.build_cmd_line(
                ['-p', project_name, '-f', compose_file_path, "up", "-d"])

            result = self._execute_clean_command(cmd_deploy, env=env)

            services = self._stack_services(project_name, compose_file_path)

            return result, services

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        project_name = kwargs['stack_name']
        docker_compose = kwargs['docker_compose']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            cmd = self.build_cmd_line(['-p', project_name, '-f', compose_file_path, 'down', '-v'])
            return self._execute_clean_command(cmd)

    update = start

    @should_connect
    def list(self, filters=None):
        pass

    @should_connect
    def log(self, list_opts):
        cmd = self.build_cmd_line(['logs'] + list_opts, binary='docker')
        return self._execute_clean_command(cmd)

    @staticmethod
    def _get_image(container_info):
        try:
            return container_info[0]['Config']['Image']
        except KeyError:
            return ''

    def _get_service_id(self, project_name, service, docker_compose_path):
        cmd = self.build_cmd_line(['-p', project_name, '-f', docker_compose_path,
                                   'ps', '-q', service])
        stdout = self._execute_clean_command(cmd)

        return yaml.load(stdout, Loader=yaml.FullLoader)

    @staticmethod
    def _get_service_ports(container_info):
        try:
            return container_info[0]['NetworkSettings']['Ports']
        except KeyError:
            return {}

    def _get_container_inspect(self, service_id):
        cmd = self.build_cmd_line(['inspect', service_id], binary='docker')

        return json.loads(self._execute_clean_command(cmd))

    def _extract_service_info(self, project_name, service, docker_compose_path):
        service_id = self._get_service_id(project_name, service, docker_compose_path)
        inspection = self._get_container_inspect(service_id)
        service_info = {
            'image': self._get_image(inspection),
            'service-id': service_id,
            'node-id': service
        }
        ports = self._get_service_ports(inspection)
        for container_port, mapping in ports.items():
            internal_port, protocol = container_port.split('/')
            try:
                external_port = mapping[0].get('HostPort')
            except (KeyError, IndexError):
                log.warning("Cannot get mapping for container port %s" % internal_port)
                continue
            except TypeError:
                log.warning("The exposed container port %s is not published to the host" % internal_port)
                continue

            if external_port:
                service_info['{}.{}'.format(protocol, internal_port)] = external_port
        return service_info

    @staticmethod
    def sanitize_command_output(output):
        new_output = [ line for line in output.splitlines() if "InsecureRequestWarning" not in line ]
        return '\n'.join(new_output)

    def _stack_services(self, project_name, docker_compose_path):
        cmd = self.build_cmd_line(['-f', docker_compose_path, 'config', '--services', '--no-interpolate'], local=True)

        stdout = self._execute_clean_command(cmd)

        services = [self._extract_service_info(project_name, service, docker_compose_path)
                    for service in stdout.splitlines()]
        return services

    @should_connect
    def stack_services(self, stack_name, raw_compose_file):
        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(raw_compose_file)
            compose_file.close()

            return self._stack_services(stack_name, compose_file_path)

    @should_connect
    def info(self):
        cmd = self.build_cmd_line(['info', '--format', '{{ json . }}'], binary='docker')

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
            return execute_cmd(cmd_login, input=password)

    @staticmethod
    def config(**kwargs):
        # required kwargs
        docker_compose = kwargs['docker_compose']
        env = kwargs['env']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            cmd = ["docker-compose", "-f", compose_file_path, "config", "-q"]
            result = execute_cmd(cmd, env=env)

        return result



