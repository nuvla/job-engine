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
        self.endpoint = self.kwargs.get('endpoint', '').replace('https://', '')
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'docker-compose-cli'

    def connect(self):
        log.info('Connecting to endpoint {}'.format(self.endpoint))
        if self.cert_file and self.key_file:
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
        return ['docker-compose', '-H', self.endpoint, '--tls', '--tlscert', self.cert_file.name,
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
                config.write(generate_registry_config(registries_auth))
                config.close()

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
        services = [DockerComposeCliConnector._extract_service_info(stack_name, service)
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
    def config_mandates_swarm(compose_file):
        """ Checks if compose file config has Swarm-specific attributes

        :param compose_file: path yaml file
        :return boolean
        """

        cmd = ["docker-compose", "-f", compose_file, "config", "-q"]
        config_output = execute_cmd(cmd)

        if "docker stack deploy" in config_output.lower():
            # there are Swarm-specific options
            return True

        return False

    def check_app_compatibility(self, **kwargs):
        """ Checks whether the app is compatible with Swarm or Docker Compose

        :return compatibility: 'swarm' or 'docker-compose' """

        # required kwargs
        docker_compose = kwargs['docker_compose']

        dc_specific_keys = ['devices', 'build', 'cap_add', 'cap_drop', 'cgroup_parent', 'container_name',
                            'depends_on', 'external_links', 'network_mode', 'restart', 'security_opt',
                            'tmpfs', 'userns_mode', 'privileged', 'domainname', 'ipc', 'mac_address', 'shm_size']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = tmp_dir_name + "/docker-compose.yaml"
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            if self.config_mandates_swarm(compose_file_path):
                # Then Swarm is enforced
                return "swarm"

            docker_compose_yaml = yaml.load(docker_compose, Loader=yaml.FullLoader)
            options = []
            for service in docker_compose_yaml['services'].values():
                options += list(service.keys())

            if set(options).intersection(set(dc_specific_keys)):
                # the module's compose file has docker-compose specific options, thus it is compose compatible
                return 'docker-compose'

            # default is swarm
            return 'swarm'


