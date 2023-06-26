# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime
import base64
import logging
import yaml
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

    def _timestamp_kubernetes(self) -> str:
        time_now = datetime.timestamp(datetime.now())
        time_stamp = \
            str(datetime.utcfromtimestamp(time_now)).replace(' ','T') \
            + '000Z'
        return time_stamp

    def _get_container_logs(self, namespace, values, since: datetime, \
                            lines = 10) -> str:
        tail_lines = lines # appease SonarCloud
        lines = int(10) # the default from the UI is 200.
        tail_lines = str(lines)
        logs_string = ''
        pod_unique_id = str(values["metadata"]["name"])
        log.debug('Unique pod ID: %s ', pod_unique_id)
        for container_name in values['spec']['containers']:
            container = str(container_name['name'])
            log.debug('Found container: %s ', container)
            since_opt = ['--since-time', since.isoformat()] \
            if since else []
            list_opts_log = ['--timestamps=true', '--tail', tail_lines, \
                '--namespace', namespace] + since_opt
            container_opts = \
                ['pod/' + pod_unique_id, '--container=' + container]
            cmd = \
                self.build_cmd_line \
                (['logs'] + container_opts + list_opts_log)
            log.debug('Generated logs command line : %s', cmd)
            header_line = "\n\nLog last " + tail_lines + \
                " lines for Container " + \
                container + " in Pod " + pod_unique_id + " \n"
            log.debug('Header line : %s', header_line)
            try:
                return_string = execute_cmd(cmd).stdout
            except Exception as ex_ret_str:
                ex_string = \
                "There is a problem getting logs from container " \
                + container + " in Pod " + pod_unique_id + "\n"
                log.info('%s %s',ex_string, ex_ret_str)
                continue
            if return_string:
                logs_string = \
                    logs_string + header_line + execute_cmd(cmd).stdout
            else:
                logs_string = logs_string + self._timestamp_kubernetes() \
                    + " There are no log entries for " + \
                    container + " in Pod " + pod_unique_id + \
                    " since " + since.isoformat() + "\n"
            log.debug('_get_container_logs logs string : %s', logs_string)
        return logs_string 

    def _get_the_pods(self, namespace, values, since: datetime, lines: int) -> str:
        logs_string = ''
        func_name = "_get_the_pods"
        log.debug('%s Starting _get_containers_logs.',func_name)
        for item in values['items']:
            if str(item["kind"]) == 'Pod':
                logs_string = logs_string + \
                    self._get_container_logs(namespace, item, since, lines)
        log.debug('%s FINAL log string : %s', func_name, logs_string)

        return logs_string

    def _get_the_logs(self, namespace, since: datetime, lines: int) -> str:
        list_opts_pods = ['-o', 'json', '--namespace', namespace]
        cmd_pods = self.build_cmd_line(['get', 'pods'] + list_opts_pods)
        log.info('Generated command line to get pods: %s', cmd_pods)
        try:
            cmd_string_out = execute_cmd(cmd_pods).stdout
        except Exception as e_json_all:
            log.info('Problem getting pods string %s ', e_json_all)
        log.info('Successfully got the pods string')
        try:
            all_json_out = json.loads(cmd_string_out)
        except Exception as e_json_out:
            log.info('Problem with loading pods JSON %s ', e_json_out)
        log.info('Successfully got the JSON')
        try:
            logs_string = \
                self._get_the_pods(namespace, all_json_out, since, lines)
        except Exception as e_logs_string:
            log.info('Problem getting logs string %s ', e_logs_string)
        # FIXME I leave for now
        log.info('Container logs string: %s', logs_string)
        return logs_string

    @should_connect
    def log(self, component: str, since: datetime, lines: int,
            **kwargs) -> str:
        namespace = kwargs['namespace']
        logs_string = self._timestamp_kubernetes() \
            + " default logging message \n"
        WORKLOAD_OBJECT_KINDS = \
            ["Deployment", "Job", "CronJob", "StatefulSet", "DaemonSet"]
        if component.split("/")[0] in WORKLOAD_OBJECT_KINDS:
            try:
                log.debug('Getting the container logs for: %s', component)
                logs_string = self._get_the_logs(namespace, since, lines)
            except Exception as ex:
                log.error('Failed getting container logs for %s: %s', component, ex)
                logs_string = \
                    self._timestamp_kubernetes() + \
                    " There was an error getting logs for component: " \
                    + str(component) + "\n"
        else:
            logs_string = \
                self._timestamp_kubernetes() + " There are no meaningful logs for " \
                + str(component) + "\n"
            log.debug('A log is requested for type Service ? : %s ',logs_string)

        return logs_string

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

