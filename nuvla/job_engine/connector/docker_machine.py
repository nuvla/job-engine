# -*- coding: utf-8 -*-

import base64
import json
import logging
import multiprocessing
import os
import shutil
import glob
import tempfile

import nuvla.job_engine.connector.machine as DockerMachine

from .connector import Connector, should_connect
from nuvla.api.resources.credential import KubeConfig

log = logging.getLogger('docker_machine')

DOCKER_MACHINE_FOLDER = os.path.expanduser("~/.docker/machine/machines")
K8S_JOIN_PORT = '6443'
SWARM_TLS_PORT = '2376'
PORTAINER_PORT = '9443'
RANCHER_PORT = '31443'
K8S_FLANNEL_VXLAN = '8472/udp'

COE_TYPE_SWARM = 'swarm'
COE_TYPE_K8S = 'kubernetes'

UTILS_DIR = os.path.join(os.path.dirname(__loader__.path), 'extra')

DEFAULT_POOL_SIZE = 5


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
                              'exoscale-disk-size',
                              'exoscale-security-group'],
                     'defaults': {'exoscale-image': 'Linux Ubuntu 18.04 LTS 64-bit'},
                     'params-map': {'cloud-vm-image': 'exoscale-image',
                                    'cloud-vm-size': 'exoscale-instance-profile',
                                    'cloud-vm-disk-size': 'exoscale-disk-size',
                                    'cloud-region': 'exoscale-availability-zone',
                                    'cloud-security-group': 'exoscale-security-group'}
                     },
        "openstack": {'env': {"openstack-password": 'OS_PASSWORD'},
                     'args': ["openstack-password",
                              "openstack-username",
                              'openstack-tenant-id',
                              'openstack-auth-url',
                              'openstack-flavor-name',
                              'openstack-image-id',
                              'openstack-net-name',
                              'openstack-domain-name',
                              'openstack-sec-groups',
                              'openstack-floatingip-pool',
                              'openstack-ssh-user'],
                     'defaults': {'openstack-ssh-user': 'root'},
                     'params-map': {'cloud-vm-image': 'openstack-image-id',
                                    'cloud-vm-size': 'openstack-flavor-name',
                                    'cloud-domain': 'openstack-domain-name',
                                    'cloud-project': 'openstack-tenant-id',
                                    'cloud-api-endpoint': 'openstack-auth-url',
                                    'cloud-network': 'openstack-net-name',
                                    'cloud-security-group': 'openstack-sec-groups',
                                    'cloud-floating-ip': 'openstack-floatingip-pool',
                                    'cloud-user': 'openstack-ssh-user'}
                     },
        "amazonec2": {'env': {'amazonec2-secret-key': 'AWS_SECRET_ACCESS_KEY'},
                      'args': ["amazonec2-access-key",
                               "amazonec2-secret-key",
                               'amazonec2-instance-type',
                               'amazonec2-region',
                               'amazonec2-root-size',
                               'amazonec2-ami',
                               'amazonec2-security-group'],
                      'defaults': {'amazonec2-open-port': '2377',
                                   # K8s starts only on 2 CPU nodes.
                                   'amazonec2-instance-type': 't2.medium'},
                      'params-map': {'cloud-vm-image': 'amazonec2-ami',
                                     'cloud-vm-size': 'amazonec2-instance-type',
                                     'cloud-vm-disk-size': 'amazonec2-root-size',
                                     'cloud-region': 'amazonec2-region',
                                     'cloud-security-group': 'amazonec2-security-group'}
                      },
        "azure": {'env': {'azure-client-secret': 'AZURE_CLIENT_SECRET'},
                  'args': ["azure-client-id",
                           "azure-client-secret",
                           "azure-subscription-id",
                           'azure-size',
                           'azure-location',
                           'azure-image'],
                  'defaults': {'azure-image': 'canonical:UbuntuServer:16.04.0-LTS:latest',
                               'azure-open-port': '2377',
                               'azure-ssh-user': 'ubuntu',
                               'azure-location': 'francecentral'},
                  'params-map': {'cloud-vm-image': 'azure-image',
                                 'cloud-vm-size': 'azure-size',
                                 'cloud-region': 'azure-location'}
                  },
        "google": {'args': ['google-project',
                            'google-username',
                            'google-zone',
                            'google-disk',
                            'google-machine-type',
                            'google-machine-image'],
                   'defaults': {'google-machine-image': 'ubuntu-os-cloud/global/images/ubuntu-1804-bionic-v20200610',
                                'google-open-port': '2377',
                                'google-machine-type': 'e2-medium',
                                'google-zone': 'europe-west3-a'},
                   'params-map': {'cloud-vm-image': 'google-machine-image',
                                  'cloud-vm-size': 'google-machine-type',
                                  'cloud-vm-disk-size': 'google-disk',
                                  'cloud-region': 'google-zone',
                                  'cloud-project': 'google-project'}
                   }
    }

    sequential_drivers = ['openstack']

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
        if self.coe_type not in [COE_TYPE_SWARM, COE_TYPE_K8S]:
            msg = f'Unknown COE type {self.coe_type}'
            log.error(msg)
            raise Exception(msg)
        self.is_swarm = self.coe_type == COE_TYPE_SWARM
        self.is_k8s = self.coe_type == COE_TYPE_K8S
        self.machine = machine

        self.coe_manager_install = False
        self.cmd_xargs, self.cmd_env = [], {}

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

    def _docker_machine_args_and_env(self, cluster_params: dict):
        # Get the xargs for this driver, from the credential, and make a
        # flat string to pass to Docker Machine
        xargs = {}
        env = {}

        extra_params = {}
        for pk, pv in cluster_params.items():
            if pk in self.driver_xargs.get('params-map', {}):
                key = self.driver_xargs.get('params-map')[pk]
                extra_params[key] = pv

        params = {**extra_params, **self.driver_credential}

        for arg in self.driver_xargs.get('args', []):
            if arg in params:
                value = params.get(arg)
                if arg in self.driver_xargs.get('env', {}):
                    env.update({self.driver_xargs['env'][arg]: value})
                else:
                    xargs[arg] = str(value)
        # Set defaults if corresponding args are missing.
        for k, v in self.driver_xargs.get('defaults', {}).items():
            if k not in xargs:
                # Adding ports
                if k.endswith('open-port'):
                    xargs[k] = [v]
                    if self.coe_manager_install:
                        if self.is_swarm:
                            xargs[k].append(PORTAINER_PORT)
                        elif self.is_k8s:
                            xargs[k].append(RANCHER_PORT)
                            xargs[k].append(K8S_FLANNEL_VXLAN)
                    if self.is_k8s:
                        xargs[k].append(K8S_JOIN_PORT)
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
        if self.is_k8s:
            port = K8S_JOIN_PORT
        else:
            port = SWARM_TLS_PORT
        return f'https://{self._vm_get_ip(inventory.manager)}:{port}'

    def _get_node(self, machine_name):
        fn = os.path.join(DOCKER_MACHINE_FOLDER, machine_name, 'config.json')
        with open(fn) as fh:
            config_b64_content = base64.b64encode(fh.read().encode('ascii'))
        fn = os.path.join(DOCKER_MACHINE_FOLDER, machine_name, 'id_rsa')
        with open(fn) as fh:
            ssh_b64_content = base64.b64encode(fh.read().encode('ascii'))

        node = {
            "node-name": machine_name,
            "manager": 'manager' in machine_name,
            "node-config-base64": config_b64_content.decode("ascii"),
            "node-ssh-base64": ssh_b64_content.decode("ascii")
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
        if self.is_k8s:
            kc = KubeConfig()
            config = kc.from_string(self._get_k8s_config(inventory))
            ca_cert, user_cert, user_key = kc.get_certs(config)
            return {'ca': ca_cert,
                    'cert': user_cert,
                    'key': user_key}
        else:
            base_path = os.path.join(DOCKER_MACHINE_FOLDER, inventory.manager)
            ca_file = os.path.join(base_path, 'ca.pem')
            cert_file = os.path.join(base_path, 'cert.pem')
            key_file = os.path.join(base_path, 'key.pem')
            return {'ca': self._load_file_content(ca_file),
                    'cert': self._load_file_content(cert_file),
                    'key': self._load_file_content(key_file)}

    @staticmethod
    def _start_machine(driver_name, machine_name, cmd_xargs, env):
        log.info(f'Provisioning {machine_name} on {driver_name} with: {" ".join(cmd_xargs)}.')
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

    @staticmethod
    def _deploy_k8s_on_node(machine_name, machine_kind, env):
        log.info(f'Copy K8s install script to {machine_name}.')
        k8s_fn = 'k8s-install.sh'
        k8s_script_remote = f'/tmp/{k8s_fn}'
        machine.scp(os.path.join(UTILS_DIR, k8s_fn),
                    f'{machine_name}:{k8s_script_remote}', env=env)

        log.info(f'Install K8s on {machine_name}')
        # IP for extra Subject Alternative Name for API server cert when host IP
        # is different from public.
        ip = machine.ip(machine_name, env=env)
        machine.ssh(machine_name,
            f'chmod +x {k8s_script_remote}; {k8s_script_remote} {machine_kind} {ip}',
            env=env)
        log.info(f'Installed K8s on {machine_name}')

    def _deploy_k8s(self, inventory: Inventory) -> dict:
        log.info('Install K8s on cluster.')
        input = [(inventory.manager, 'manager', self.cmd_env)]
        for worker_name in inventory.workers:
            input.append((worker_name, 'worker', self.cmd_env))

        pool = multiprocessing.Pool(len(inventory.all()))
        try:
            outputs = pool.starmap(self._deploy_k8s_on_node, input)
            pool.close()
            pool.join()
        except Exception as ex:
            log.error(f'Failed to install K8s on cluster: {ex}')
            pool.terminate()
        log.info('Installed K8s on cluster.')

        join_token_worker = self._k8s_join_token(inventory.manager, self.cmd_env)
        join_token_manager = f'{join_token_worker} --control-plane'

        if inventory.workers:
            log.info('Join K8s workers.')
            for worker_name in inventory.workers:
                log.info(f'Join {worker_name} to K8s cluster.')
                machine.ssh(worker_name, f'sudo {join_token_worker}', env=self.cmd_env)
        else:
            log.info('No workers to join K8s cluster.')

        return {'manager': join_token_manager,
                'worker': join_token_worker}

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
            self._start_machines(inventory, machine_names, nodes)

        log.info('VMs started and Docker installed.')

        # Collect nodes' management info (provisioner specific).
        for machine_name in inventory.all():
            nodes.append(self._get_node(machine_name))
        log.info('Nodes collected.')

    def _start_machines(self, inventory, machine_names, nodes):
        inputs = []
        for machine_name in machine_names:
            inputs.append((self.driver_name,
                           machine_name,
                           self.cmd_xargs,
                           self.cmd_env))
        try:
            if self.driver_name in self.sequential_drivers:
                self._start_machines_sequential(inputs)
            else:
                self._start_machines_parallel(inputs, machine_names)
        except Exception as ex:
            log.error(f'Failed to run start machines: {ex}')
            # Collect machines that filed to start but still registered locally.
            for machine_name in inventory.all():
                try:
                    nodes.append(self._get_node(machine_name))
                except Exception:
                    pass
            raise ex

    def _start_machines_sequential(self, inputs):
        for args in inputs:
            self._start_machine(*args)

    def _start_machines_parallel(self, inputs, machine_names):
        pool_size = min(DEFAULT_POOL_SIZE, len(machine_names))
        pool = multiprocessing.Pool(pool_size)
        try:
            err_codes = pool.starmap(self._start_machine, inputs)
            pool.close()
            pool.join()
        except Exception as ex:
            pool.terminate()
            raise ex

    def _create_swarm(self, inventory: Inventory) -> dict:
        # Initialize Docker Swarm on manager.
        log.info('Initialising swarm on manager.')
        self._swarm_init(inventory)
        log.info('Initialised swarm on manager.')
        join_token_worker = f'sudo {self._swarm_join_token_worker(inventory)}'
        join_token_manager = f'sudo {self._swarm_join_token_manager(inventory)}'
        log.debug(f'Obtained cluster join tokens from {inventory.manager}')

        # Join workers to the cluster, if any.
        if inventory.workers:
            if not join_token_worker:
                raise Exception(f'Failed to get swarm join token from {inventory.manager}')
            pool_size = min(DEFAULT_POOL_SIZE, len(inventory.workers))
            pool = multiprocessing.Pool(pool_size)
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

        return {'manager': join_token_manager,
                'worker': join_token_worker}

    def _set_on_nodes_manager(self, nodes: list, key, value):
        for i, node in enumerate(nodes):
            if node.get('manager', False):
                nodes[i][key] = value
                break

    def _set_join_tokens_on_manager(self, nodes, join_tokens):
        self._set_on_nodes_manager(nodes, 'join-tokens', join_tokens)

    def _set_kubeconfig_on_manager(self, inventory: Inventory, nodes: list):
        if self.is_k8s:
            self._set_on_nodes_manager(nodes, 'kube-config',
                                       self._get_k8s_config(inventory))

    @staticmethod
    def _push_ssh_keys_to_machine(machine_name, keys_pub, env):
        add_keys_sh = 'ssh-add-keys.sh'
        ssh_keys_fn = 'ssh_keys.pub'
        machine.scp(keys_pub, f'{machine_name}:{ssh_keys_fn}', env=env)
        machine.scp(os.path.join(UTILS_DIR, add_keys_sh), f'{machine_name}:{add_keys_sh}', env=env)
        cmd = f'chmod +x {add_keys_sh} && ./{add_keys_sh} {ssh_keys_fn}'
        machine.ssh(machine_name, cmd, env=env)

    def _push_ssh_keys(self, inventory: Inventory, ssh_keys: list):
        if not ssh_keys:
            return
        log.info('Push ssh keys to nodes.')
        _, keys_pub_fn = tempfile.mkstemp()
        try:
            with open(keys_pub_fn, 'w+t') as fh:
                for ssh_key in ssh_keys:
                    fh.write(f'{ssh_key.strip()}\n')
            input = [(x, keys_pub_fn, self.cmd_env) for x in inventory.all()]
            pool_size = min(DEFAULT_POOL_SIZE, len(inventory.all()))
            pool = multiprocessing.Pool(pool_size)
            try:
                pool.starmap(self._push_ssh_keys_to_machine, input)
                pool.close()
                pool.join()
            except Exception as ex:
                log.info(f'Failed to push user ssh keys to nodes: {ex}')
                pool.terminate()
                raise ex
        finally:
            os.unlink(keys_pub_fn)
        log.info('Pushed ssh keys to nodes.')

    def _install_portainer(self, inventory):
        compose = 'portainer-swarm.yaml'
        machine.scp(os.path.join(UTILS_DIR, compose),
                    f'{inventory.manager}:{compose}',
                    env=self.cmd_env)
        cmd = f'sudo docker stack deploy --compose-file={compose} portainer'
        machine.ssh(inventory.manager, cmd, self.cmd_env)
        ip = self._vm_get_ip(inventory.manager)
        endpoint = f'https://{ip}:{PORTAINER_PORT}'
        return endpoint

    def _install_rancher(self, inventory):
        install_fn = 'install-rancher.sh'
        machine.scp(os.path.join(UTILS_DIR, install_fn),
                    f'{inventory.manager}:{install_fn}',
                    env=self.cmd_env)
        cmd = f'chmod +x {install_fn}; ./{install_fn}'
        machine.ssh(inventory.manager, cmd, self.cmd_env)
        ip = self._vm_get_ip(inventory.manager)
        endpoint = f'https://{ip}:{RANCHER_PORT}'
        return endpoint

    def _install_coe_manager(self, inventory):
        mgr_name = self.is_swarm and 'Portainer' or 'Rancher'
        log.info(f'Install COE manager {mgr_name}.')
        endpoint = None
        try:
            if self.is_swarm:
                endpoint = self._install_portainer(inventory)
            else:
                endpoint = self._install_rancher(inventory)
        except Exception as ex:
            log.error(f'Failed to install COE manager {mgr_name}: {ex}')
        log.info(f'Installed COE manager {mgr_name}.')
        return endpoint

    def _provision_init(self, cluster_params):
        multiplicity = int(cluster_params.get('multiplicity'))
        if multiplicity < 1:
            raise Exception('Refusing to provision cluster of multiplicity less than 1.')
        if self.is_k8s:
            multiplicity += 1
        inventory = Inventory(self.machine_base_name, multiplicity=multiplicity)

        self.coe_manager_install = cluster_params.get('coe-manager-install', False)
        self.ssh_keys = cluster_params.get('ssh-keys', [])
        self.cmd_xargs, self.cmd_env = self._docker_machine_args_and_env(cluster_params)

        return inventory

    @should_connect
    def provision(self, cluster_params: dict):
        inventory = self._provision_init(cluster_params)

        nodes = []
        try:
            msg = f'{self.coe_type.title()} cluster of size {len(inventory.all())} on {self.driver_name}'
            log.info(f'Provisioning COE {msg}.')
            self._provision_cluster(nodes, inventory)
            self._push_ssh_keys(inventory, self.ssh_keys)
            self._create_coe(inventory, nodes)
            log.info(f'Provisioned COE {msg}.')

            result = {'creds': self._coe_credentials(inventory),
                      'endpoint': self._coe_endpoint(inventory),
                      'nodes': nodes}

            if self.coe_manager_install:
                result['coe-manager-endpoint'] = self._install_coe_manager(inventory)

            return result

        except Exception as ex:
            log.error(f'Failed to provision COE cluster: {ex}')
            self.clear_connection()
            if len(nodes) > 0:
                self.stop(nodes=nodes)
            raise ex

    def _create_coe(self, inventory: Inventory, nodes: list):
        log.info('Creating COE.')
        if self.is_swarm:
            join_tokens = self._create_swarm(inventory)
        else:
            join_tokens = self._deploy_k8s(inventory)
            self._set_kubeconfig_on_manager(inventory, nodes)
        self._set_join_tokens_on_manager(nodes, join_tokens)
        log.info('Created COE.')

    @staticmethod
    def _terminate_node(node, env):
        node_name = node["node-name"]
        log.info(f'Terminating node: {node_name}')
        machine_folder = os.path.join(DOCKER_MACHINE_FOLDER, node_name)
        os.makedirs(machine_folder, exist_ok=True)
        with open(os.path.join(machine_folder, 'config.json'), 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-config-base64"].encode('ascii')).decode('ascii'))
        res = machine.rm(machine=node_name, force=True, env=env)
        log.info(f'Terminated node: {node_name}')
        return res

    @should_connect
    def terminate(self, **kwargs):
        n = len(kwargs['nodes'])
        if n < 1:
            log.warning('No nodes provided to terminate.')
            return
        log.info(f'Terminating {n} nodes on {self.driver_name}.')

        if self.driver_name == 'google':
            self.cmd_env['GOOGLE_APPLICATION_CREDENTIALS'] = self._build_gce_adc()

        pool = multiprocessing.Pool(min(DEFAULT_POOL_SIZE, n))
        try:
            deleted = pool.starmap(self._terminate_node,
                                   [(x, self.cmd_env) for x in kwargs['nodes']])
            pool.close()
            pool.join()
        except Exception as ex:
            log.error(f'Failed to terminate machines on {self.driver_name}: {ex}')
            log.error(f'Delete the nodes manually from {self.driver_name}: {kwargs["nodes"]}')
            pool.terminate()
            raise ex
        log.info(f'Deleted {sum(deleted)} out of {n} nodes on {self.driver_name}.')
        return deleted

    @staticmethod
    def _stop_node(node, env):
        node_name = node["node-name"]
        log.info(f'Stopping node: {node_name}')
        machine_folder = os.path.join(DOCKER_MACHINE_FOLDER, node_name)
        os.makedirs(machine_folder, exist_ok=True)
        with open(os.path.join(machine_folder, 'config.json'), 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-config-base64"].encode('ascii')).decode('ascii'))
        res = machine.stop(machine=node_name, env=env)
        log.info(f'Stopped node: {node_name}')
        return res

    @should_connect
    def stop(self, **kwargs):
        n = len(kwargs['nodes'])
        if n < 1:
            log.warning('No nodes provided to .')
            return
        log.info(f'Stopping {n} nodes on {self.driver_name}.')

        if self.driver_name == 'google':
            self.cmd_env['GOOGLE_APPLICATION_CREDENTIALS'] = self._build_gce_adc()

        pool = multiprocessing.Pool(min(DEFAULT_POOL_SIZE, n))
        try:
            stopped = pool.starmap(self._stop_node,
                                   [(x, self.cmd_env) for x in kwargs['nodes']])
            pool.close()
            pool.join()
        except Exception as ex:
            log.error(f'Failed to run stop machines on {self.driver_name}: {ex}')
            log.error(f'Stop the nodes manually from {self.driver_name}: {kwargs["nodes"]}')
            pool.terminate()
            raise ex
        log.info(f'Stopped {sum(stopped)} out of {n} nodes on {self.driver_name}.')
        return stopped

    @staticmethod
    def _start_node(node, env):
        node_name = node["node-name"]
        log.info(f'Starting node: {node_name}')
        machine_folder = os.path.join(DOCKER_MACHINE_FOLDER, node_name)
        os.makedirs(machine_folder, exist_ok=True)
        with open(os.path.join(machine_folder, 'config.json'), 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-config-base64"].encode('ascii')).decode('ascii'))
        ssh_key_fn = os.path.join(machine_folder, 'id_rsa')
        with open(ssh_key_fn, 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-ssh-base64"].encode('ascii')).decode('ascii'))
            os.chmod(ssh_key_fn, 0o400)
        res = machine.start(machine=node_name, env=env)
        log.info(f'Started node: {node_name}')
        return res

    @should_connect
    def start(self, **kwargs):
        n = len(kwargs['nodes'])
        if n < 1:
            log.warning('No nodes provided to .')
            return
        log.info(f'Starting {n} nodes on {self.driver_name}.')

        if self.driver_name == 'google':
            self.cmd_env['GOOGLE_APPLICATION_CREDENTIALS'] = self._build_gce_adc()

        pool = multiprocessing.Pool(min(DEFAULT_POOL_SIZE, n))
        try:
            stopped = pool.starmap(self._start_node,
                                   [(x, self.cmd_env) for x in kwargs['nodes']])
            pool.close()
            pool.join()
        except Exception as ex:
            log.error(f'Failed to run start machines on {self.driver_name}: {ex}')
            log.error(f'Start the nodes manually from {self.driver_name}: {kwargs["nodes"]}')
            pool.terminate()
            raise ex
        log.info(f'Started {sum(stopped)} out of {n} nodes on {self.driver_name}.')
        return stopped

    def list(self):
        return self.machine.ls()
