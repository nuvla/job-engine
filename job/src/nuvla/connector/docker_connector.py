# -*- coding: utf-8 -*-

import re
import logging
import requests
from collections import defaultdict
from tempfile import NamedTemporaryFile
from connector import Connector, should_connect


def tree():
    return defaultdict(tree)


def instantiate_from_cimi(api_connector, api_credential):
    return DockerConnector(api_connector, api_credential)


class DockerConnector(Connector):

    def __init__(self, api_connector, api_credential):
        super(DockerConnector, self).__init__(api_connector, api_credential)

        self.cert = api_credential.get('key').replace("\\n", "\n")
        self.key = api_credential.get('secret').replace("\\n", "\n")
        self.endpoint = api_connector.get('endpoint')

        self.docker_api = requests.Session()
        self.docker_api.verify = False
        self.docker_api.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    @property
    def connector_type(self):
        return 'Docker'

    def connect(self):
        logging.warn('Connecting with connector {} and credential {}'.format(self.api_connector['id'],
                                                                             self.api_credential['id']))
        auth_file = NamedTemporaryFile(bufsize=0, delete=True)
        auth_file.write(self.cert + '\n' + self.key)
        auth_file.flush()
        self.docker_api.cert = auth_file.name
        return auth_file

    def clear_connection(self, connect_result):
        connect_result.close()

    @should_connect
    def start(self, api_deployment):
        service_json = tree()
        service_json['Name'] = 'service-test'  # FIXME
        service_json['TaskTemplate']['ContainerSpec']['Image'] = api_deployment['module']['content']['image']

        working_dir = None  # FIXME
        if working_dir:
            service_json['TaskTemplate']['ContainerSpec']['Dir'] = working_dir

        env = None  # FIXME
        if env:
            service_json['TaskTemplate']['ContainerSpec']['Env'] = env

        cpu_ratio = None  # FIXME
        if cpu_ratio:
            cpu_ratio_nano_secs = int(float(cpu_ratio) * 1000000000)
            service_json['TaskTemplate']['Resources']['Limits']['NanoCPUs'] = cpu_ratio_nano_secs
            service_json['TaskTemplate']['Resources']['Reservations']['NanoCPUs'] = cpu_ratio_nano_secs

        ram_giga_bytes = None  # FIXME
        if ram_giga_bytes:
            ram_bytes = int(float(ram_giga_bytes) * 1073741824)
            service_json['TaskTemplate']['Resources']['Limits']['MemoryBytes'] = ram_bytes
            service_json['TaskTemplate']['Resources']['Reservations']['MemoryBytes'] = ram_bytes

        restart_policy = None  # FIXME
        if restart_policy:
            service_json['TaskTemplate']['RestartPolicy']['Condition'] = restart_policy

        cmd = None  # FIXME
        if cmd:
            service_json['TaskTemplate']['ContainerSpec']['command'] = [cmd]

        args = None  # FIXME
        if args:
            service_json['TaskTemplate']['ContainerSpec']['args'] = args

        ports = []

        ports_opt = []  # FIXME

        mounts_opt = []  # FIXME

        service_json['EndpointSpec']['Ports'] = DockerConnector.get_ports_mapping(ports, ports_opt)

        service_json['TaskTemplate']['ContainerSpec']['Mounts'] = DockerConnector.get_mounts(mounts_opt)

        vm = self.docker_api.post(self._get_full_url("services/create"), json=service_json).json()
        # TODO: wait for IP before returning
        return vm

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
        return vm["ID"]

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
        if len(response.keys()) == 1 and response.has_key("message"):
            raise Exception(response["message"])

    @staticmethod
    def get_container_os_preparation_script(ssh_pub_key=''):
        centos_install_script = \
            'yum clean all && yum install -y wget python openssh-server && ' + \
            'mkdir -p /var/run/sshd && mkdir -p $HOME/.ssh/ && ' + \
            'echo "{}" > $HOME/.ssh/authorized_keys && '.format(ssh_pub_key) + \
            'sed -i "s/PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config && ' + \
            'ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key -N "" && ' + \
            'ssh-keygen -f /etc/ssh/ssh_host_ed25519_key -N "" -t ed25519 && ' + \
            'ssh-keygen -f /etc/ssh/ssh_host_ecdsa_key -N "" -t ecdsa && ' + \
            '/usr/sbin/sshd'
        ubuntu_install_script = \
            'apt-get update && apt-get install -y wget python python-pkg-resources openssh-server && ' + \
            'mkdir -p /var/run/sshd && mkdir -p $HOME/.ssh/ && ' + \
            'echo "{}" > $HOME/.ssh/authorized_keys && '.format(ssh_pub_key) + \
            'sed -i "s/PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config && ' + \
            '/usr/sbin/sshd'
        alpine_install_script = \
            'apk add wget python openssh && ' + \
            'ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N "" -t rsa && ' + \
            'ssh-keygen -f /etc/ssh/ssh_host_dsa_key -N "" -t dsa && ' + \
            'mkdir -p /var/run/sshd && mkdir -p $HOME/.ssh/ && ' + \
            'echo "{}" > $HOME/.ssh/authorized_keys && '.format(ssh_pub_key) + \
            'sed -i "s/PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config && ' + \
            '/usr/sbin/sshd'

        return 'command -v yum; if [ $? -eq 0 ]; then {}; fi && '.format(centos_install_script) + \
               'command -v apt-get; if [ $? -eq 0 ]; then {}; fi && '.format(ubuntu_install_script) + \
               'command -v apk; if [ $? -eq 0 ]; then {}; fi'.format(alpine_install_script)

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

