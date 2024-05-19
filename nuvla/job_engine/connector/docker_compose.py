# -*- coding: utf-8 -*-
import json
import logging
import os
import yaml

from datetime import datetime
from tempfile import TemporaryDirectory

from .connector import Connector, should_connect
from .utils import (create_tmp_file,
                    execute_cmd,
                    generate_registry_config,
                    join_stderr_stdout,
                    LOCAL,
                    remove_protocol_from_url)

log = logging.getLogger('docker_compose')

docker_compose_filename = 'docker-compose.yaml'

DEFAULT_PULL_TIMEOUT = "1200"  # Default timeout for docker compose pull commands
DEFAULT_DOCKER_TIMEOUT = "300"  # Default timeout for docker commands


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerCompose(
        cert=api_credential.get('cert').replace("\\n", "\n"),
        key=api_credential.get('key').replace("\\n", "\n"),
        endpoint=api_infrastructure_service.get('endpoint'))


class DockerCompose(Connector):

    def __init__(self, **kwargs):
        super(DockerCompose, self).__init__(**kwargs)

        self.cert = kwargs.get('cert')
        self.key = kwargs.get('key')
        self.cert_file = None
        self.key_file = None

        endpoint = kwargs.get('endpoint', '') or LOCAL
        self.endpoint = remove_protocol_from_url(endpoint)

    @property
    def connector_type(self):
        return 'docker-compose-cli'

    def connect(self):
        log.info('Connecting to endpoint "{}"'.format(self.endpoint))
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

    def build_cmd_line(self, list_cmd, local=False, docker_command='compose'):
        if local or self.endpoint == LOCAL:
            remote_tls = []
        else:
            remote_tls = ['-H', self.endpoint, '--tls',
                          '--tlscert', self.cert_file.name,
                          '--tlskey', self.key_file.name,
                          '--tlscacert', self.cert_file.name]

        return ['docker'] + remote_tls + [docker_command] + list_cmd

    def _execute_clean_command(self, cmd, **kwargs):
        try:
            return execute_cmd(cmd, **kwargs)
        except Exception as e:
            error = self.sanitize_command_output(str(e))
            raise RuntimeError(error)

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        docker_compose = kwargs['docker_compose']
        project_name = kwargs['name']
        env = kwargs['env']
        registries_auth = kwargs['registries_auth']

        pull_timeout = os.getenv('JOB_PULL_TIMEOUT') or DEFAULT_PULL_TIMEOUT
        docker_timeout = os.getenv('JOB_DOCKER_TIMEOUT') or DEFAULT_DOCKER_TIMEOUT

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = f'{tmp_dir_name}/{docker_compose_filename}'
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            if registries_auth:
                config_path = tmp_dir_name + "/config.json"
                config = open(config_path, 'w')
                config.write(generate_registry_config(registries_auth))
                config.close()
                env['DOCKER_CONFIG'] = tmp_dir_name

            files = kwargs['files']
            if files:
                for file_info in files:
                    file_path = tmp_dir_name + "/" + file_info['file-name']
                    file = open(file_path, 'w')
                    file.write(file_info['file-content'])
                    file.close()

            cmd_pull = self.build_cmd_line(
                ['-p', project_name, '-f', compose_file_path, 'pull'])

            cmd_deploy = self.build_cmd_line(
                ['-p', project_name, '-f', compose_file_path, 'up', '-d',
                 '--remove-orphans'])

            env['DOCKER_CLIENT_TIMEOUT'] = pull_timeout
            env['COMPOSE_HTTP_TIMEOUT'] = pull_timeout
            result = ''
            try:
                result += join_stderr_stdout(
                    self._execute_clean_command(
                        cmd_pull,
                        env=env,
                        timeout=int(pull_timeout)))
            except Exception as e:
                result += str(e)

            env['DOCKER_CLIENT_TIMEOUT'] = docker_timeout
            env['COMPOSE_HTTP_TIMEOUT'] = docker_timeout
            result += join_stderr_stdout(
                self._execute_clean_command(
                    cmd_deploy,
                    env=env,
                    timeout=int(docker_timeout)))

            services = self._get_services(project_name, compose_file_path, env)

            return result, services

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        project_name = kwargs['name']
        docker_compose = kwargs['docker_compose']
        env = kwargs.get('env')

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = f'{tmp_dir_name}/{docker_compose_filename}'
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            cmd = self.build_cmd_line(
                ['-p', project_name, '-f', compose_file_path, 'down'])
            return join_stderr_stdout(self._execute_clean_command(cmd, env=env))

    update = start

    @should_connect
    def list(self, filters=None):
        pass

    @should_connect
    def log(self, component: str, since: datetime, lines: int, **kwargs) -> str:
        deployment_uuid = kwargs['deployment_uuid']
        docker_compose = kwargs['docker_compose']
        env = kwargs.get('env')

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = f'{tmp_dir_name}/{docker_compose_filename}'
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()
            service_id = self._get_service_id(deployment_uuid, component,
                                              compose_file_path, env)
        if service_id:
            since_opt = ['--since', since.isoformat()] if since else []
            list_opts = ['-t', '--tail', str(lines)] + since_opt + [service_id]
            cmd = self.build_cmd_line(list_opts, docker_command='logs')
            return execute_cmd(cmd, sterr_in_stdout=True).stdout
        else:
            return f'{datetime.utcnow().isoformat()} [Failed to find container "{component}" for deployment {deployment_uuid}]'

    @staticmethod
    def _get_image(container_info):
        try:
            return container_info[0]['Config']['Image']
        except KeyError:
            return ''

    def _get_service_id(self, project_name, service, docker_compose_path, env):
        cmd = self.build_cmd_line(['-p', project_name,
                                   '-f', docker_compose_path,
                                   'ps', '-q', '-a', service])
        stdout = self._execute_clean_command(cmd, env=env).stdout

        return yaml.load(stdout, Loader=yaml.FullLoader)

    @staticmethod
    def _get_service_ports(container_info):
        try:
            return container_info[0]['NetworkSettings']['Ports']
        except KeyError:
            return {}

    def _get_container_inspect(self, service_id, env):
        cmd = self.build_cmd_line([service_id], docker_command='inspect')

        return json.loads(self._execute_clean_command(cmd, env=env).stdout)

    def _extract_service_info(self, project_name, service, docker_compose_path, env):
        service_id = self._get_service_id(project_name, service, docker_compose_path, env)
        if not service_id:
            log.warning(f'Cannot find container for service "{service}"')
            return

        inspection = self._get_container_inspect(service_id, env)
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
                log.warning(f'Cannot get mapping for container port {internal_port}')
                continue
            except TypeError:
                log.warning(f'The exposed container port {internal_port} is not published to the host')
                continue

            if external_port:
                service_info[
                    '{}.{}'.format(protocol, internal_port)] = external_port
        return service_info

    @staticmethod
    def sanitize_command_output(output):
        new_output = [line for line in str(output).splitlines() if
                      "InsecureRequestWarning" not in line]
        return '\n'.join(new_output)

    def _get_services(self, project_name, docker_compose_path, env):
        cmd = self.build_cmd_line(
            ['-f', docker_compose_path, 'config', '--services'], local=True)

        stdout = self._execute_clean_command(cmd, env=env).stdout

        services = []
        for service in stdout.splitlines():
            service_info = self._extract_service_info(project_name, service, docker_compose_path, env)
            if service_info:
                services.append(service_info)

        return services

    @should_connect
    def get_services(self, name, env, **kwargs):
        compose_file_content = kwargs['compose_file']
        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = f'{tmp_dir_name}/{docker_compose_filename}'
            compose_file = open(compose_file_path, 'w')
            compose_file.write(compose_file_content)
            compose_file.close()

            return self._get_services(name, compose_file_path, env)

    @should_connect
    def info(self):
        cmd = self.build_cmd_line(['--format', '{{ json . }}'], docker_command='info')

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
        serveraddress = remove_protocol_from_url(kwargs['serveraddress'])

        with TemporaryDirectory() as tmp_dir_name:
            config_path = tmp_dir_name + "/config.json"
            config = open(config_path, 'w')
            json.dump({'auths': {'': {}}}, config)
            config.close()
            cmd_login = ['docker', '--config', tmp_dir_name, 'login',
                         '--username', username, '--password-stdin',
                         'https://' + serveraddress]
            return execute_cmd(cmd_login, input=password).stdout

    @staticmethod
    def config(**kwargs):
        # required kwargs
        docker_compose = kwargs['docker_compose']
        env = kwargs['env']

        with TemporaryDirectory() as tmp_dir_name:
            compose_file_path = f'{tmp_dir_name}/{docker_compose_filename}'
            compose_file = open(compose_file_path, 'w')
            compose_file.write(docker_compose)
            compose_file.close()

            cmd = ["docker", "compose", "-f", compose_file_path, "config", "-q"]
            result = execute_cmd(cmd, env=env).stdout

        return result
