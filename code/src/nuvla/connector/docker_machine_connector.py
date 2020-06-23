# -*- coding: utf-8 -*-

import base64
import json
import logging
import multiprocessing
import os
import shutil
import glob

import nuvla.connector.machine as DockerMachine

from .connector import Connector, should_connect
from nuvla.api.resources.credential import KubeConfig

log = logging.getLogger('docker_machine_connector')

DOCKER_MACHINE_FOLDER = os.path.expanduser("~/.docker/machine/machines")
K8S_JOIN_PORT = 6443
SWARM_TLS_PORT = 2376

COE_TYPE_SWARM = 'swarm'
COE_TYPE_K8S = 'kubernetes'


def instantiate_from_cimi(infra_service_coe: dict, cloud_driver_credential: dict):
    coe_type = infra_service_coe['subtype']
    # GCE doesn't like VM names longer than 61 chars.
    mname = coe_type == COE_TYPE_K8S and 'k8s' or coe_type
    machine_base_name = f"{infra_service_coe['id'].split('/')[1]}-{mname}"
    return DockerMachineConnector(
        driver_credential=cloud_driver_credential,
        driver_name=cloud_driver_credential['subtype'].split('-')[-1],
        coe_type=coe_type,
        machine_base_name=machine_base_name)


machine = DockerMachine.Machine()


class Inventory:

    def __init__(self, node_base_name, multiplicity=1):
        self.manager = None
        self.workers = []
        self.add_manager(f'{node_base_name}-manager-1')
        for i in range(1, multiplicity):
            worker_name = f'{node_base_name}-worker-{i}'
            self.add_worker(worker_name)

    def add_manager(self, manager):
        self.manager = manager

    def add_worker(self, worker):
        self.workers.append(worker)

    def all(self):
        return [self.manager] + self.workers


class DockerMachineConnector(Connector):
    XARGS = {
        "exoscale": {'env': {"exoscale-api-secret-key": 'EXOSCALE_API_SECRET'},
                     'args': ["exoscale-api-secret-key",
                              "exoscale-api-key",
                              'exoscale-availability-zone',
                              'exoscale-image',
                              'exoscale-instance-profile',
                              'exoscale-security-group'],
                     'defaults': {'exoscale-image': 'Linux Ubuntu 18.04 LTS 64-bit'}
                     },
        "amazonec2": {'env': {'amazonec2-secret-key': 'AWS_SECRET_ACCESS_KEY'},
                      'args': ["amazonec2-access-key",
                               "amazonec2-secret-key",
                               'amazonec2-instance-type',
                               'amazonec2-region',
                               'amazonec2-ami'],
                      'defaults': {# 'amazonec2-ami': 'ami-08c757228751c5335',
                                   'amazonec2-open-port': '2377'}
                      },
        "azure": {'env': {'azure-client-secret': 'AZURE_CLIENT_SECRET'},
                  'args': ["azure-client-id",
                           "azure-client-secret",
                           "azure-subscription-id",
                           'azure-size',
                           'azure-location'],
                  'defaults': {'azure-image': 'canonical:UbuntuServer:16.04.0-LTS:latest',
                               'azure-open-port': '2377',
                               'azure-location': 'francecentral'}
                  },
        "google": {'args': ['google-project',
                            'google-username',
                            'google-zone',
                            'google-machine-type'],
                   'defaults': {'google-machine-image': 'ubuntu-os-cloud/global/images/ubuntu-1804-bionic-v20200610',
                                'google-open-port': '2377',
                                'google-zone': 'europe-west3-a'}
                   }
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.driver_name = self.kwargs.get("driver_name")

        if self.driver_name not in self.XARGS:
            msg = f'There are no Docker Machine arguments {self.XARGS} ' \
                  f'available for driver {self.driver_name}.'
            log.error(msg)
            raise NotImplementedError(msg)
        else:
            self.driver_xargs = self.XARGS[self.driver_name]

        self.driver_credential = self.kwargs["driver_credential"]
        name = self.kwargs.get("machine_base_name").replace(" ", "-")
        self.machine_base_name = f'nuvla-{name}'
        self.coe_type = self.kwargs.get('coe_type', COE_TYPE_SWARM).lower()
        self.machine = machine

        self.cmd_xargs, self.cmd_env = self._docker_machine_args_and_env()

    def _build_gce_adc(self) -> str:
        """Returns path to the GCE ADC file after building its content from
        the provided driver credentials. If the same named file already exists
        its content is not touched.
        """

        # Put Google ADC along the machines into the folder starting with
        # machine base name so that it gets auto reaped during cleanup.
        abc_path = os.path.join(DOCKER_MACHINE_FOLDER,
                                f'{self.machine_base_name}-google-adc')
        adc_file = os.path.join(abc_path, 'adc.json')
        if os.path.exists(adc_file):
            return adc_file

        adc_keys = ['client-id',
                    'client-secret',
                    'refresh-token']
        adc = {'type': 'authorized_user'}
        for k in adc_keys:
            if k not in self.driver_credential:
                raise Exception(f'{k} is missing in google driver credentials.')
            adc[k.replace('-', '_')] = self.driver_credential[k]
        os.makedirs(abc_path, exist_ok=True)
        with open(adc_file, 'w') as fh:
            fh.write(json.dumps(adc))
        return adc_file

    def _docker_machine_args_and_env(self):
        # Get the xargs for this driver, from the credential, and make a
        # flat string to pass to Docker Machine
        xargs = {}
        env = {}

        for arg in self.driver_xargs.get('args', []):
            if arg in self.driver_credential:
                value = self.driver_credential.get(arg)
                if arg in self.driver_xargs.get('env', {}):
                    env.update({self.driver_xargs['env'][arg]: value})
                else:
                    xargs[arg] = str(value)
        # Set defaults if corresponding args are missing.
        for k, v in self.driver_xargs.get('defaults', {}).items():
            if k not in xargs:
                # TODO: refactor.
                # Add K8s join port to firewall.
                if k.endswith('open-port') and self.coe_type == COE_TYPE_K8S:
                    xargs[k] = [v, str(K8S_JOIN_PORT)]
                else:
                    xargs[k] = v
        cmd_xargs = []
        for k, v in xargs.items():
            if isinstance(v, list):
                for _v in v:
                    cmd_xargs.extend([f'--{k}', _v])
            else:
                cmd_xargs.extend([f'--{k}', v])

        if self.driver_name == 'google':
            env['GOOGLE_APPLICATION_CREDENTIALS'] = self._build_gce_adc()

        return cmd_xargs, env

    @property
    def connector_type(self):
        return 'docker-machine'

    def connect(self):
        version = self.machine.version()
        log.info(f"Using docker-machine. Version: {version}")

    @staticmethod
    def delete_folder(path):
        shutil.rmtree(path)

    def clear_connection(self, connect_result=None):
        path = os.path.join(DOCKER_MACHINE_FOLDER, self.machine_base_name)
        for p in glob.glob(path + '*'):
            try:
                shutil.rmtree(p)
            except FileNotFoundError:
                pass

    @staticmethod
    def validate_action(response):
        """Takes the raw response from _start_container_in_docker
        and checks whether the service creation request was successful or not"""
        pass

    def _vm_get_ip(self, machine_name):
        return machine.ip(machine=machine_name, env=self.cmd_env)

    def _coe_endpoint(self, inventory: Inventory):
        if self.coe_type == COE_TYPE_K8S:
            port = K8S_JOIN_PORT
        elif self.coe_type == COE_TYPE_SWARM:
            port = SWARM_TLS_PORT
        else:
            raise Exception(f'Do not know how to get endpoint for {self.coe_type}')
        return f'https://{self._vm_get_ip(inventory.manager)}:{port}'

    def _get_node(self, machine_name):
        fn = os.path.join(DOCKER_MACHINE_FOLDER, machine_name, 'config.json')
        with open(fn) as fh:
            b64_content = base64.b64encode(fh.read().encode('ascii'))

        node = {
            "node-name": machine_name,
            "manager": 'manager' in machine_name,
            "node-config-base64": b64_content.decode("ascii")
        }

        return node

    def _swarm_init(self, inventory: Inventory):
        ip = self._vm_get_ip(inventory.manager)
        command = \
            f'sudo docker swarm init --force-new-cluster --advertise-addr {ip}'
        return machine.ssh(inventory.manager, command, self.cmd_env)

    def _swarm_join_token_worker(self, inventory: Inventory):
        return self._swarm_join_token(inventory.manager, 'worker', self.cmd_env)

    def _swarm_join_token_manager(self, inventory: Inventory):
        return self._swarm_join_token(inventory.manager, 'manager', self.cmd_env)

    @staticmethod
    def _swarm_join_token(machine_name, kind, env):
        """kind - worker or manager"""
        kinds = ['worker', 'manager']
        if kind not in kinds:
            raise Exception(f'Docker Swarm token kind can be {kinds}')
        command = f'sudo docker swarm join-token {kind}'
        res = machine.ssh(machine_name, command, env=env)
        token = ''
        for line in res:
            if line.strip().startswith('docker swarm join'):
                token = line.strip()
        return token

    @staticmethod
    def _swarm_join(worker_name, swarm_join_token, env):
        return machine.ssh(worker_name, swarm_join_token, env=env)

    @staticmethod
    def _load_file_content(path):
        with open(path, 'r') as file:
            return file.read()

    def _coe_credentials(self, inventory: Inventory) -> dict:
        if self.coe_type == COE_TYPE_K8S:
            kc = KubeConfig()
            config = kc.from_string(self._get_k8s_config(inventory))
            ca_cert, user_cert, user_key = kc.get_certs(config)
            return {'ca': ca_cert,
                    'cert': user_cert,
                    'key': user_key}
        elif self.coe_type == COE_TYPE_SWARM:
            base_path = os.path.join(DOCKER_MACHINE_FOLDER, inventory.manager)
            ca_file = os.path.join(base_path, 'ca.pem')
            cert_file = os.path.join(base_path, 'cert.pem')
            key_file = os.path.join(base_path, 'key.pem')
            return {'ca': self._load_file_content(ca_file),
                    'cert': self._load_file_content(cert_file),
                    'key': self._load_file_content(key_file)}
        else:
            raise Exception(f'Do not know how to get credentials for {self.coe_type}')

    @staticmethod
    def _start_machine(driver_name, machine_name, cmd_xargs, env):
        log.info(f'Provisioning {machine_name}.')
        err_code = machine.create(machine_name, driver=driver_name,
                                  xarg=cmd_xargs, env=env)
        log.info(f'Provisioned {machine_name}.')
        return err_code

    @staticmethod
    def _k8s_join_token(manager_name, env):
        command = 'sudo kubeadm token create --print-join-command'
        res = machine.ssh(manager_name, command, env=env)
        token = ''
        for line in res:
            if line.strip().startswith('kubeadm join'):
                token = line.strip()
        return token

    def _deploy_k8s(self, inventory: Inventory) -> dict:
        log.info('Copy K8s install script to nodes.')

        k8s_fn = 'k8s-install.sh'
        k8s_path = os.path.join(os.path.dirname(__loader__.path), k8s_fn)
        k8s_script_remote = f'/tmp/{k8s_fn}'
        for machine_name in inventory.all():
            log.info(f'Copy K8s install to {machine_name}.')
            machine.scp(k8s_path, f'{machine_name}:{k8s_script_remote}',
                        env=self.cmd_env)

        log.info('Install K8s on manager')
        machine.ssh(inventory.manager,
                    f'chmod +x {k8s_script_remote}; {k8s_script_remote} manager',
                    env=self.cmd_env)

        # TODO: make it concurrent.
        for worker_name in inventory.workers:
            log.info(f'Install K8s to {worker_name}.')
            machine.ssh(worker_name,
                        f'chmod +x {k8s_script_remote}; {k8s_script_remote} worker',
                        env=self.cmd_env)

        log.info('Installed K8s on the cluster.')

        join_token_worker = self._k8s_join_token(inventory.manager, self.cmd_env)
        join_token_manager = f'{join_token_worker} --control-plane'

        if inventory.workers:
            log.info('Join K8s workers.')
            for worker_name in inventory.workers:
                log.info(f'Join {worker_name} to K8s cluster.')
                machine.ssh(worker_name, f'sudo {join_token_worker}', env=self.cmd_env)
        else:
            log.info('No workers to join K8s cluster.')

        return {'join_tokens':
                    {'manager': join_token_manager,
                     'worker': join_token_worker},
                'kind': COE_TYPE_K8S}

    def _get_k8s_config(self, inventory: Inventory) -> str:
        log.info('Get kubectl config from manager.')
        kube_config_file = '/tmp/kube-config'
        machine.scp(f'{inventory.manager}:~/.kube/config', kube_config_file,
                    env=self.cmd_env)
        with open(kube_config_file) as fh:
            config = fh.read()
        try:
            os.unlink(kube_config_file)
        except:
            pass
        return config

    def _provision_cluster(self, nodes: list, inventory: Inventory):
        # Provision VMs on CSP and install Docker Swarm.

        machine_names = inventory.all()

        dm_ca = os.path.expanduser('~/.docker/machine/certs/ca.pem')
        if not os.path.exists(dm_ca):
            log.info('No certs for docker-machine. Initial run.')
            # Provision manager separately.
            # NB!
            # This race prevents concurrent instantiation of manager and workers:
            # https://github.com/docker/machine/issues/3845
            # Once 'docker-machine create' was run ones and local certs were
            # generated, it's OK to run the machines creation concurrently.
            try:
                err_code = self._start_machine(self.driver_name, inventory.manager,
                                               self.cmd_xargs, self.cmd_env)
            except Exception as ex:
                log.error(f'Failed to start manager: {ex}')
                # Try collecting manager that failed to start, but might still
                # be registered locally.
                try:
                    nodes.append(self._get_node(inventory.manager))
                except Exception:
                    pass
                raise ex

            machine_names = inventory.workers

        if machine_names:
            inputs = []
            for machine_name in machine_names:
                inputs.append((self.driver_name,
                               machine_name,
                               self.cmd_xargs,
                               self.cmd_env))
            pool = multiprocessing.Pool(processes=len(machine_names))
            try:
                err_codes = pool.starmap(self._start_machine, inputs)
                pool.close()
                pool.join()
            except Exception as ex:
                log.error(f'Failed to run start machines: {ex}')
                pool.terminate()
                # Collect machines that filed to start but still registered locally.
                for machine_name in inventory.all():
                    try:
                        nodes.append(self._get_node(machine_name))
                    except Exception:
                        pass
                raise ex

        log.info('VMs started and Docker installed.')

        # Collect nodes' management info (provisioner specific).
        for machine_name in inventory.all():
            nodes.append(self._get_node(machine_name))
        log.info('Nodes collected.')

    def _create_swarm(self, inventory: Inventory) -> dict:
        # Initialize Docker Swarm on manager.
        log.info('Initialising swarm on manager.')
        self._swarm_init(inventory)
        log.info('Initialised swarm on manager.')
        join_token_worker = f'sudo {self._swarm_join_token_worker(inventory)}'
        join_token_manager = f'sudo {self._swarm_join_token_manager(inventory)}'
        log.debug(f'Obtained cluster join tokens from {inventory.manager}')

        # Join workers to the cluster, if any.
        join_tokens = {}
        if inventory.workers:
            if not join_token_worker:
                raise Exception(f'Failed to get swarm join token from {inventory.manager}')
            pool = multiprocessing.Pool(processes=len(inventory.workers))
            try:
                log.info(f'Joining workers to cluster.')
                input = [(x, join_token_worker, self.cmd_env) for x in inventory.workers]
                joined = pool.starmap(self._swarm_join, input)
                pool.close()
                pool.join()
                log.info(f'Joined workers to cluster.')
            except Exception as ex:
                log.error(f'Failed to join workers to cluster: {ex}')
                pool.terminate()
                raise ex
            join_tokens = \
                {'join_tokens':
                     {'manager': join_token_manager,
                      'worker': join_token_worker},
                 'kind': COE_TYPE_SWARM}

        return join_tokens

    def _set_kubeconfig_on_manager(self, inventory: Inventory, nodes: list):
        if self.coe_type == COE_TYPE_K8S:
            config = self._get_k8s_config(inventory)
            for i, node in enumerate(nodes):
                if node.get('manager', False):
                    nodes[i]['kube-config'] = config
                    break

    @should_connect
    def start(self, cluster_params: dict):
        multiplicity = cluster_params.get('multiplicity', 1)
        if multiplicity < 1:
            raise Exception('Refusing to provision cluster of multiplicity less than 1.')
        if self.coe_type == COE_TYPE_K8S:
            multiplicity += 1
        inventory = Inventory(self.machine_base_name, multiplicity=multiplicity)

        nodes = []
        try:
            msg = f'{self.coe_type.title()} cluster of size {multiplicity} on {self.driver_name}'
            log.info(f'Provisioning COE {msg}.')
            self._provision_cluster(nodes, inventory)
            join_tokens = self._create_coe(inventory, nodes)
            log.info(f'Provisioned COE {msg}.')
            log.debug(f'COE cluster: {self.list()}')
            # TODO: Do we need to return join tokens for later cluster expansion?
            return self._coe_credentials(inventory), \
                   self._coe_endpoint(inventory), \
                   nodes
        except Exception as ex:
            log.error(f'COE cluster failed to start: {ex}')
            self.clear_connection()
            if len(nodes) > 0:
                self.stop(nodes=nodes)
            raise ex

    def _create_coe(self, inventory: Inventory, nodes: list) -> dict:
        log.info('Creating COE.')
        if self.coe_type == COE_TYPE_SWARM:
            join_tokens = self._create_swarm(inventory)
        elif self.coe_type == COE_TYPE_K8S:
            join_tokens = self._deploy_k8s(inventory)
            self._set_kubeconfig_on_manager(inventory, nodes)
        else:
            raise Exception(f'Do not know how to create COE {self.coe_type}')
        log.info('Created COE.')

        return join_tokens

    @staticmethod
    def _stop_node(node, env):
        node_name = node["node-name"]
        log.info(f'Stopping node: {node_name}')
        machine_folder = os.path.join(DOCKER_MACHINE_FOLDER, node_name)
        os.makedirs(machine_folder, exist_ok=True)
        with open(os.path.join(machine_folder, 'config.json'), 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-config-base64"].encode('ascii')).decode('ascii'))
        res = machine.rm(machine=node_name, force=True, env=env)
        log.info(f'Stopped node: {node_name}')
        return res

    @should_connect
    def stop(self, **kwargs):
        n = len(kwargs['nodes'])
        if n < 1:
            log.warning('No nodes provided to stop.')
            return
        log.info(f'Stopping {n} nodes on {self.driver_name}.')
        pool = multiprocessing.Pool(processes=n)
        try:
            stopped = pool.starmap(self._stop_node,
                                   [(x, self.cmd_env) for x in kwargs['nodes']])
            pool.close()
            pool.join()
        except Exception as ex:
            log.error(f'Failed to run stop machines on {self.driver_name}: {ex}')
            log.error(f'Delete the nodes manually from {self.driver_name}: {kwargs["nodes"]}')
            pool.terminate()
            raise ex
        log.info(f'Stopped {sum(stopped)} out of {n} nodes on {self.driver_name}.')
        return stopped

    def list(self):
        return self.machine.ls()
