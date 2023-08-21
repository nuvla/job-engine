# -*- coding: utf-8 -*-

import json
import logging
import base64
from collections import defaultdict
from tempfile import NamedTemporaryFile

import requests

from .connector import Connector, ConnectorError, should_connect
from .registry import image_dict_to_str
from .utils import timestr2dtime, extract_host_from_url

"""
Service is a set of tasks. Service doesn't have a state, but tasks do.

       task state
      /    |    \
running shutdown accepted <- DesiredState
        /   |   \
 shutdown failed rejected <- Status.State

Single replica task spawns a new container.

"""

log = logging.getLogger('docker_service')

bytes_per_mib = 1048576

as_nanos = 1000000000

tolerance = 1.1  # 10% leeway on resource requirements


def tree():
    return defaultdict(tree)


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerService(cert=api_credential.get('cert').replace("\\n", "\n"),
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


class DockerService(Connector):

    @staticmethod
    def service_image_digest(service):
        """
        Returns image id and digest as two-tuple.

        :param service: dict, docker service
        :return: tuple, (image id, digest)
        """
        image, digest = '', ''
        if service:
            img = service['Spec']['TaskTemplate']['ContainerSpec']['Image']
            parts = img.split('@')
            image = parts[0]
            if len(parts) > 1:
                digest = parts[1]
        return image, digest

    @staticmethod
    def service_get_last_timestamp(service):
        s_created_at = timestr2dtime(service.attrs['CreatedAt'])
        s_updated_at = timestr2dtime(service.attrs['UpdatedAt'])
        return s_created_at > s_updated_at and s_created_at or s_updated_at

    def __init__(self, **kwargs):
        super(DockerService, self).__init__(**kwargs)

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

    @staticmethod
    def format_env(env):
        container_env = []
        for key, value in env.items():
            if value:
                container_env.append('{}={}'.format(key, value))
        return container_env

    @staticmethod
    def service_dict(**kwargs):
        # Mandatory kwargs
        image = kwargs['image']

        # Optional kwargs
        service_name = kwargs.get('name')
        env = kwargs.get('env')
        mounts_opt = kwargs.get('mounts_opt', [])
        ports_opt = kwargs.get('ports_opt', [])
        working_dir = kwargs.get('working_dir')
        cpus = kwargs.get('cpus')
        memory = kwargs.get('memory')
        cmd = kwargs.get('cmd')
        args = kwargs.get('args')
        restart_policy_condition = kwargs.get('restart_policy_condition')
        restart_policy_delay = kwargs.get('restart_policy_delay')
        restart_policy_max_attempts = kwargs.get('restart_policy_max_attempts')
        restart_policy_window = kwargs.get('restart_policy_window')

        #
        # The fields that are supported by the Docker API are documented here:
        # https://docs.docker.com/engine/api/v1.37/#39-services
        #
        service = tree()

        if service_name:
            service['Name'] = service_name

        service['TaskTemplate']['ContainerSpec']['Image'] = image_dict_to_str(image)

        if working_dir:
            service['TaskTemplate']['ContainerSpec']['Dir'] = working_dir

        if env:
            service['TaskTemplate']['ContainerSpec']['Env'] = DockerService.format_env(env)

        if cpus:
            nano_cpus_soft = int(float(cpus) * as_nanos)
            nano_cpus_hard = int(float(cpus) * as_nanos * tolerance)
            service['TaskTemplate']['Resources']['Limits']['NanoCPUs'] = nano_cpus_hard
            service['TaskTemplate']['Resources']['Reservations']['NanoCPUs'] = nano_cpus_soft

        if memory:
            ram_bytes_soft = int(float(memory) * bytes_per_mib)
            ram_bytes_hard = int(float(memory) * bytes_per_mib * tolerance)
            service['TaskTemplate']['Resources']['Limits']['MemoryBytes'] = ram_bytes_hard
            service['TaskTemplate']['Resources']['Reservations']['MemoryBytes'] = ram_bytes_soft

        if restart_policy_condition:
            service['TaskTemplate']['RestartPolicy']['Condition'] = restart_policy_condition

        if restart_policy_delay:
            service['TaskTemplate']['RestartPolicy']['Delay'] = restart_policy_delay

        if restart_policy_max_attempts:
            service['TaskTemplate']['RestartPolicy']['MaxAttempts'] = restart_policy_max_attempts

        if restart_policy_window:
            service['TaskTemplate']['RestartPolicy']['Window'] = restart_policy_window

        if cmd:
            service['TaskTemplate']['ContainerSpec']['command'] = [cmd]

        if args:
            service['TaskTemplate']['ContainerSpec']['args'] = args

        service['EndpointSpec']['Ports'] = DockerService.construct_ports_mapping(ports_opt)

        service['TaskTemplate']['ContainerSpec']['Mounts'] = \
            DockerService.construct_mounts(mounts_opt)

        return service

    def registry_auth_header(self, registry_auth):
        registry_auth_json = json.dumps(registry_auth).encode('ascii')
        x_registry_auth = base64.b64encode(registry_auth_json)
        self.docker_api.headers['X-Registry-Auth'] = x_registry_auth

    @should_connect
    def start(self, **kwargs):
        """
        :param kwargs: see `DockerConnector.service_dict()` for of `kwargs`
        :return: None, json - service
        """

        registry_auth = kwargs.get('registry_auth')
        if registry_auth:
            self.registry_auth_header(registry_auth)

        response = self.docker_api.post(self._get_full_url("services/create"),
                                        json=self.service_dict(**kwargs)).json()

        self.validate_action(response)

        service = self.docker_api.get(
            self._get_full_url('services/{}'.format(response['ID']))).json()

        self.validate_action(service)

        return None, service

    @should_connect
    def stop(self, **kwargs):
        # Mandatory kwargs
        service_id = kwargs['service_id']

        response = self.docker_api.delete(self._get_full_url("services/{}".format(service_id)))
        if response.status_code not in {200, 404}:
            self.validate_action(response.json())

    @should_connect
    def update(self, **kwargs):
        """
        :param kwargs: see `DockerConnector.service_dict()` for of `kwargs`
        :return: None, json - service
        """
        service_name = kwargs['service_name']

        registry_auth = kwargs.get('registry_auth')
        if registry_auth:
            self.registry_auth_header(registry_auth)

        services = self._list(filters={'name': service_name})
        if len(services) >= 1:
            service = services[0]
        else:
            raise ConnectorError('No service named {} when updating service.'.format(service_name))

        service_id      = service['ID']
        service_version = service['Version']['Index']

        service_spec = self.service_dict(**kwargs)

        response = self.docker_api.post(self._get_full_url('services/{}/update'.format(service_id)),
                                        params=[('version', service_version)],
                                        json=service_spec).json()
        self.validate_action(response)

        services = self._list(filters={'name': service_name})
        if len(services) >= 1:
            return None, [services[0]]
        else:
            raise ConnectorError('No service named {} after service update.'.format(service_name))

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
        return self._list(filters=filters)

    def _list(self, filters=None):
        """Version w/o connection wrapper.
        See `list()` for description of parameters.
        """
        request_url = self._get_full_url("services")
        params = {'filters': convert_filters(filters) if filters else None}
        services_list = self.docker_api.get(request_url, params=params).json()
        if not isinstance(services_list, list):
            self.validate_action(services_list)
        return services_list

    def service_get(self, sname):
        services = self.list(filters={'name': sname})
        if len(services) >= 1:
            return services[0]
        else:
            return {}

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

    def service_replicas(self, sname):
        """
        Returns number of running and desired replicas of `sname` service as two-tuple
        (#running, #desired).
        Returns (-1, -1) in case `sname` service is not found.
        Returns (#running, -1), in case `sname` service is not in Replicated or Global
        mode.
        -1 indicates an error.

        :param sname: str, service name.
        :return: (int, int)
        """
        desired = self.service_replicas_desired(sname)
        if desired < 0:
            return -1, -1
        running = self.service_replicas_running(sname)
        return running, desired

    def service_replicas_desired(self, sname):
        """
        Returns number of desired replicas of `sname` service.
        Returns -1 in case `sname` service is not found.
        Returns -1 in case `sname` service is not in Replicated or Global mode.
        -1 indicates an error.

        :param sname: str, service name.
        :return: int
        """
        services = self.list(filters={"name": sname})
        if len(services) != 1:
            return -1
        mode = services[0]['Spec']['Mode']
        if 'Replicated' in mode:
            return mode['Replicated']['Replicas']
        elif 'Global' in mode:
            return len(self.nodes_list_active())
        else:
            return -1

    def service_replicas_running(self, sname):
        return self.service_tasks(filters={'service': sname,
                                           'desired-state': 'running'})

    @should_connect
    def nodes_list(self, availability=None):
        """
        Returns list of nodes.

        :param availability: str
        :return: list
        """
        nodes = self.docker_api.get(self._get_full_url("nodes")).json()
        if availability:
            return list(filter(lambda x:
                               x.get('Spec', {}).get('Availability') == availability, nodes))
        else:
            return nodes

    def nodes_list_active(self):
        return self.nodes_list(availability='active')

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
                volume_opts = m_opt.get('volume-options')
                if volume_opts:
                    mount_map['VolumeOptions']['DriverConfig']['Options'] = volume_opts
                mounts.append(mount_map)
        return mounts

    @should_connect
    def info(self):
        """
        Returns node system info as JSON.

        :return: json
        """
        info = self.docker_api.get(self._get_full_url("info")).json()
        server_errors = info.get('ServerErrors', [])
        if len(server_errors) > 0:
            raise Exception(server_errors[0])
        return info
