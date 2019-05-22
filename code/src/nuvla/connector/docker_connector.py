# -*- coding: utf-8 -*-

import re
import json
import logging
import requests
from collections import defaultdict
from tempfile import NamedTemporaryFile

from .connector import Connector, ConnectorError, should_connect


log = logging.getLogger('docker_connector')

def tree():
    return defaultdict(tree)


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerConnector(cert=api_credential.get('cert').replace("\\n", "\n"),
                           key=api_credential.get('key').replace("\\n", "\n"),
                           endpoint=api_infrastructure_service.get('endpoint'))


def convert_filters(filters):
    result = {}
    for k, v in filters.items():
        if isinstance(v, bool):
            v = 'true' if v else 'false'
        if not isinstance(v, list):
            v = [v, ]
        result[k] = [
            str(item) if not isinstance(item, str) else item
            for item in v
        ]
    return json.dumps(result)


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
        log.info('Connecting to endpoint {}'.format(self.endpoint))
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

        service_json['TaskTemplate']['ContainerSpec']['Image'] = DockerConnector.construct_image_name(image)

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

        service_json['EndpointSpec']['Ports'] = DockerConnector.construct_ports_mapping(ports_opt)

        service_json['TaskTemplate']['ContainerSpec']['Mounts'] = DockerConnector.construct_mounts(mounts_opt)

        response = self.docker_api.post(self._get_full_url("services/create"), json=service_json).json()

        self.validate_action(response)

        service = self.docker_api.get(self._get_full_url('services/{}'.format(response['ID']))).json()

        self.validate_action(service)

        return service

    @should_connect
    def stop(self, ids):
        for service_id in ids:
            response = self.docker_api.delete(self._get_full_url("services/{}".format(service_id)))
            if response.status_code not in {200, 404}:
                self.validate_action(response.json())

    @should_connect
    def list(self, filters=None):
        """
        Returns list of services with optional `filters` applied.

        :param filters:
            id=<service id>
            label=<service label>
            mode=["replicated"|"global"]
            name=<service name>
        :return: list of services
        """
        request_url = self._get_full_url("services")
        params = {'filters': convert_filters(filters) if filters else None}
        services_list = self.docker_api.get(request_url, params=params).json()
        if not isinstance(services_list, list):
            self.validate_action(services_list)
        return services_list

    @should_connect
    def service_tasks(self, filters=None):
        """
        Returns list of tasks with optional `filters` applied.

        :param filters:
            desired-state=(running | shutdown | accepted)
            id=<task id>
            label=key or label="key=value"
            name=<task name>
            node=<node id or name>
            service=<service name>
        :return: list
        """
        params = {'filters': convert_filters(filters) if filters else None}
        return self.docker_api.get(self._get_full_url("tasks"), params=params).json()

    @should_connect
    def service_replicas(self, sname, tasks_filters=None):
        """
        Returns number of running and desired replicas of `sname` service as two-tuple
        (#running, #desired).
        Returns (-1, -1) in case `sname` service is not found.
        Returns (#running, -1), in case `sname` service is not in Replicated or Global
        mode.
        -1 indicates an error.

        :param sname: str, service name.
        :param tasks_filters: dict, see `service_tasks()`->`filters` for dict spec.
        :return: (int, int)
        """
        running = -1
        desired = -1
        services = self.list(filters={"name": sname})
        if len(services) != 1:
            return running, desired
        mode = services[0]['Spec']['Mode']
        if 'Replicated' in mode:
            desired = mode['Replicated']['Replicas']
        elif 'Global' in mode:
            desired = len(self.nodes_list_active())
        if tasks_filters:
            tasks_filters.update({'service': sname})
        else:
            tasks_filters = {'service': sname}
        tasks = self.service_tasks(filters=tasks_filters)
        return len(tasks), desired

    def service_replicas_running(self, sname):
        return self.service_replicas(sname, tasks_filters={'desired-state': 'running'})

    @should_connect
    def nodes_list(self, availability=None):
        """
        Returns list of nodes.

        :param availability: str
        :return: list
        """
        nodes = self.docker_api.get(self._get_full_url("nodes")).json()
        if availability:
            return list(filter(lambda x: x.get('Spec', {}).get('Availability') == availability, nodes))
        else:
            return nodes

    def nodes_list_active(self):
        return self.nodes_list(availability='active')

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
    def construct_ports_mapping(ports_opt):
        ports = []
        if ports_opt:
            for port_opt in ports_opt:
                port_mapping = {'Protocol': port_opt.get('protocol', 'tcp'),
                                'TargetPort': port_opt['target-port']}
                port_published = port_opt.get('published-port')
                if port_published:
                    port_mapping['PublishedPort'] = port_published
                ports.append(port_mapping)
        return ports

    @staticmethod
    def construct_mounts(mounts_opt):
        mounts = []
        if mounts_opt:
            for m_opt in mounts_opt:
                mount_map = tree()
                mount_map['Type'] = m_opt['mount-type']
                mount_map['ReadOnly'] = m_opt.get('read-only', False)
                source = m_opt.get('source')
                if source:
                    mount_map['Source'] = m_opt['source']
                mount_map['Target'] = m_opt['target']
                mount_map['VolumeOptions']['DriverConfig']['Options'] = m_opt.get('volume-options', [])
                mounts.append(mount_map)
        return mounts

    @staticmethod
    def construct_image_name(image):
        tag = image.get('tag')
        registry = image.get('registry')
        repository = image.get('repository')

        image_name = image['image-name']
        if tag:
            image_name = ':'.join([image_name, tag])

        if repository:
            image_name = '/'.join([repository, image_name])

        if registry:
            image_name = '/'.join([registry, image_name])

        return image_name
