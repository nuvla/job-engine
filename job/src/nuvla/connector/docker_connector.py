# -*- coding: utf-8 -*-

import re
import logging
import requests
from collections import defaultdict
from tempfile import NamedTemporaryFile
from .connector import Connector, ConnectorError, should_connect


def tree():
    return defaultdict(tree)


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                           key=api_credential.get('key').replace("\\n", "\n"),
                           endpoint=api_infrastructure_service.get('endpoint'))


class DockerConnector(Connector):

    def __init__(self, **kwargs):
        super(DockerConnector, self).__init__(**kwargs)

        # Mandatory kwargs
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']
        self.endpoint = self.kwargs['endpoint']

        self.docker_api = requests.Session()
        self.docker_api.verify = False
        self.docker_api.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    @property
    def connector_type(self):
        return 'Docker'

    def connect(self):
        logging.info('Connecting to endpoint {}'.format(self.endpoint))
        auth_file = NamedTemporaryFile(delete=True)
        auth_text = self.cert + '\n' + self.key
        auth_file.write(auth_text.encode())
        auth_file.flush()
        self.docker_api.cert = auth_file.name
        return auth_file

    def clear_connection(self, connect_result):
        if connect_result:
            connect_result.close()

    @should_connect
    def start(self, **start_kwargs):
        # Mandatory start_kwargs
        image = start_kwargs['image']

        # Optional start_kwargs
        service_name = start_kwargs.get('service_name')
        env = start_kwargs.get('env')
        mounts_opt = start_kwargs.get('mounts_opt', [])
        ports_opt = start_kwargs.get('ports_opt', [])
        working_dir = start_kwargs.get('working_dir')
        cpu_ratio = start_kwargs.get('cpu_ratio')
        ram_giga_bytes = start_kwargs.get('ram_giga_bytes')
        restart_policy = start_kwargs.get('restart_policy')
        cmd = start_kwargs.get('cmd')
        args = start_kwargs.get('args')

        service_json = tree()

        if service_name:
            service_json['Name'] = service_name

        service_json['TaskTemplate']['ContainerSpec']['Image'] = image

        if working_dir:
            service_json['TaskTemplate']['ContainerSpec']['Dir'] = working_dir

        if env:
            service_json['TaskTemplate']['ContainerSpec']['Env'] = env

        if cpu_ratio:
            cpu_ratio_nano_secs = int(float(cpu_ratio) * 1000000000)
            service_json['TaskTemplate']['Resources']['Limits']['NanoCPUs'] = cpu_ratio_nano_secs
            service_json['TaskTemplate']['Resources']['Reservations']['NanoCPUs'] = cpu_ratio_nano_secs

        if ram_giga_bytes:
            ram_bytes = int(float(ram_giga_bytes) * 1073741824)
            service_json['TaskTemplate']['Resources']['Limits']['MemoryBytes'] = ram_bytes
            service_json['TaskTemplate']['Resources']['Reservations']['MemoryBytes'] = ram_bytes

        if restart_policy:
            service_json['TaskTemplate']['RestartPolicy']['Condition'] = restart_policy

        if cmd:
            service_json['TaskTemplate']['ContainerSpec']['command'] = [cmd]

        if args:
            service_json['TaskTemplate']['ContainerSpec']['args'] = args

        ports = []

        service_json['EndpointSpec']['Ports'] = DockerConnector.get_ports_mapping(ports, ports_opt)

        service_json['TaskTemplate']['ContainerSpec']['Mounts'] = DockerConnector.get_mounts(mounts_opt)

        response = self.docker_api.post(self._get_full_url("services/create"), json=service_json).json()

        self.validate_action(response)

        container = self.docker_api.get(self._get_full_url('services/{}'.format(response['ID']))).json()

        self.validate_action(container)

        return container

    @should_connect
    def stop(self, ids):
        for service_id in ids:
            response = self.docker_api.delete(self._get_full_url("services/{}".format(service_id)))
            if response.status_code != 200:
                self.validate_action(response.json())

    @should_connect
    def list(self):
        request_url = self._get_full_url("services")
        services_list = self.docker_api.get(request_url).json()
        if not isinstance(services_list, list):
            self.validate_action(services_list)
        return services_list

    def extract_vm_id(self, vm):
        return vm['ID']

    def extract_vm_ip(self, vm):
        return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', self.endpoint).group('host')

    def extract_vm_state(self, vm):
        return 'running'

    def extract_vm_ports_mapping(self, vm):
        published_ports_list = [":".join([str(pp.get("Protocol")),
                                          str(pp.get('PublishedPort')),
                                          str(pp.get('TargetPort'))])
                                for pp in vm.get('Endpoint', {}).get('Ports', [])]

        return " ".join(published_ports_list)

    def _get_full_url(self, action):
        return "{}/{}".format(self.endpoint, action)

    @staticmethod
    def validate_action(response):
        """Takes the raw response from _start_container_in_docker
        and checks whether the service creation request was successful or not"""
        if len(response.keys()) == 1 and 'message' in response:
            raise ConnectorError(response['message'])

    @staticmethod
    def extend_ports_range(string_port):
        if string_port.strip():
            range_port = string_port.split('-')
            range_start = int(range_port[0])
            range_end = int(range_port[0]) if len(range_port) == 1 else int(range_port[1])
            return range(range_start, range_end + 1)
        return None

    @staticmethod
    def get_ports_mapping(ports, publish_ports):
        if publish_ports:
            for publish_port in publish_ports:
                temp = publish_port.split(':')
                protocol = temp[0].lower()
                range_target = DockerConnector.extend_ports_range(temp[2])
                range_published = DockerConnector.extend_ports_range(temp[1])
                explicit_published = range_published is not None
                for i in range(len(range_target)):
                    port_mapping = {'Protocol': protocol,
                                    'TargetPort': range_target[i]}
                    if explicit_published:
                        port_mapping['PublishedPort'] = range_published[i]
                    ports.append(port_mapping)
        return ports

    @staticmethod
    def transform_in_kv_list(string):
        result = []
        aggregator = None
        for el in string.split(','):
            token = None
            if el.endswith('"'):
                token = ','.join([aggregator, el[:-1]])
                aggregator = None
            elif aggregator:
                aggregator = ','.join([aggregator, el])
            elif el.startswith('"'):
                aggregator = el[1:]
            else:
                token = el

            if token:
                kv = token.split('=', 1)
                result.append([kv[0], kv[1] if len(kv) == 2 else True])
        return result

    @staticmethod
    def get_mounts(mounts_opt):
        mounts = []
        for mount in mounts_opt:
            mount_map = tree()
            mount_map['Type'] = 'volume'
            mount_map['ReadOnly'] = False
            for k, v in DockerConnector.transform_in_kv_list(mount):
                if k == 'readonly':
                    mount_map['ReadOnly'] = v
                elif k == 'type':
                    mount_map['Type'] = v
                elif k == 'src':
                    mount_map['Source'] = v
                elif k == 'dst':
                    mount_map['Target'] = v
                elif k == 'volume-opt':
                    opt = v.split('=', 1)
                    mount_map['VolumeOptions']['DriverConfig']['Options'][opt[0]] = opt[1]
                elif k == 'volume-driver':
                    mount_map['VolumeOptions']['DriverConfig']['Name'] = v
                elif k == 'bind-propagation':
                    mount_map['BindOptions']['Propagation'] = v
                elif k == 'tmpfs-size':
                    mount_map['TmpfsOptions']['SizeBytes'] = int(v)
                elif k == 'tmpfs-mode':
                    mount_map['TmpfsOptions']['Mode'] = int(v)
                elif k == 'consistency':
                    mount_map['Consistency'] = v
            mounts.append(mount_map)
        return mounts
