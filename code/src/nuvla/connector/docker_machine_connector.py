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

log = logging.getLogger('docker_machine_connector')


def instantiate_from_cimi(infra_service_coe: dict, cloud_driver_credential: dict):
    coe_type = infra_service_coe['subtype']
    machine_base_name = f"{infra_service_coe['id'].split('/')[1]}-{coe_type}"
    return DockerMachineConnector(
        driver_credential=cloud_driver_credential,
        driver_name=cloud_driver_credential['subtype'].split('-')[-1],
        coe_type=coe_type,
        machine_base_name=machine_base_name)


DOCKER_MACHINE_FOLDER = os.path.expanduser("~/.docker/machine/machines")
K8S_JOIN_PORT = 6443

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
                      'defaults': {'amazonec2-ami': 'ami-08c757228751c5335',
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
        self.coe_type = self.kwargs.get('coe_type', 'swarm')
        self.machine = machine

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

    def _get_full_url(self):
        return self.machine.url(machine=self.machine_base_name)

    @staticmethod
    def validate_action(response):
        """Takes the raw response from _start_container_in_docker
        and checks whether the service creation request was successful or not"""
        pass

    def _vm_get_ip(self, machine_name):
        return self.machine.ip(machine=machine_name)

    def _coe_endpoint(self, machine_name):
        # TODO: Swarm and K8s.
        endpoint = f'https://{self._vm_get_ip(machine_name)}:2376'
        return endpoint

    def _vm_get_id(self):
        return self.machine_base_name

    def _vm_get_state(self):
        if self.machine.status(machine=self.machine_base_name):
            return "Running"
        else:
            return "Stopped"

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

    def swarm_init(self, inventory: Inventory):
        ip = self._vm_get_ip(inventory.manager)
        command = \
            f'sudo docker swarm init --force-new-cluster --advertise-addr {ip}'
        return self.machine.ssh(inventory.manager, command)

    @classmethod
    def swarm_join_token_worker(cls, inventory: Inventory):
        return cls._swarm_join_token(inventory.manager, 'worker')

    @classmethod
    def swarm_join_token_manager(cls, inventory: Inventory):
        return cls._swarm_join_token(inventory.manager, 'manager')

    @staticmethod
    def _swarm_join_token(machine_name, kind):
        """kind - worker or manager"""
        kinds = ['worker', 'manager']
        if kind not in kinds:
            raise Exception(f'Docker Swarm token kind can be {kinds}')
        command = f'sudo docker swarm join-token {kind}'
        res = machine.ssh(machine_name, command)
        token = ''
        for line in res:
            if line.strip().startswith('docker swarm join'):
                token = line.strip()
        return token

    @staticmethod
    def swarm_join(input):
        return machine.ssh(input['worker_name'],
                           input['swarm_join_token'])

    @staticmethod
    def load_file_content(path):
        with open(path, 'r') as file:
            return file.read()

    def _coe_credentials(self, machine_name) -> dict:
        if self.coe_type == 'kubernetes':
            # TODO: implement!!!
            ca_file = ''
            cert_file = ''
            key_file = ''
        else:
            base_path = os.path.join(DOCKER_MACHINE_FOLDER, machine_name)
            ca_file = os.path.join(base_path, 'ca.pem')
            cert_file = os.path.join(base_path, 'cert.pem')
            key_file = os.path.join(base_path, 'key.pem')
        return {"key": self.load_file_content(key_file),
                "ca": self.load_file_content(ca_file),
                "cert": self.load_file_content(cert_file)}

    def docker_machine_args_and_env(self):
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
                if k.endswith('open-port') and self.coe_type == 'kubernetes':
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
            # TODO: Extract. Google ADC.
            adc_keys = ['client_id',
                        'client_secret',
                        'refresh_token']
            adc = {'type': 'authorized_user'}
            for k in adc_keys:
                if k not in self.driver_credential:
                    raise Exception(f'{k} is missing in google driver credentials.')
                adc[k] = self.driver_credential[k]
            # Put Google ADC along the machines into the folder starting with
            # machine base name so that it gets auto reaped during cleanup.
            abc_path = os.path.join(DOCKER_MACHINE_FOLDER,
                                    f'{self.machine_base_name}-google-adc')
            os.makedirs(abc_path, exist_ok=True)
            adc_file = os.path.join(abc_path, 'adc.json')
            with open(adc_file, 'w') as fh:
                fh.write(json.dumps(adc))
            env['GOOGLE_APPLICATION_CREDENTIALS'] = adc_file

        return cmd_xargs, env

    @staticmethod
    def _start_machine(input):
        driver_name = input['driver_name']
        machine_name = input['machine_name']
        cmd_xargs = input['cmd_xargs']
        env = input['env']
        log.info(f'Provisioning {machine_name}.')
        err_code = machine.create(machine_name, driver=driver_name, xarg=cmd_xargs,
                             env=env)
        log.info(f'Provisioned {machine_name}.')
        return err_code

    @staticmethod
    def k8s_join_token(manager_name):
        command = 'sudo kubeadm token create --print-join-command'
        res = machine.ssh(manager_name, command)
        token = ''
        for line in res:
            if line.strip().startswith('kubeadm join'):
                token = line.strip()
        return token

    def kubernetes_install(self, inventory):

        log.info('Copy K8s install script to nodes.')
        k8s_script_remote = '/tmp/k8s-install.sh'
        for machine_name in inventory.all():
            log.info(f'Copy K8s install to {machine_name}.')
            machine.scp('./k8s-install.sh', f'{machine_name}:{k8s_script_remote}')

        log.info('Install K8s on manager')
        machine.ssh(inventory.manager,
                    f'chmod +x {k8s_script_remote}; {k8s_script_remote} manager')

        # TODO: make it concurrent.
        for worker_name in inventory.workers:
            log.info(f'Install K8s to {worker_name}.')
            machine.ssh(worker_name,
                        f'chmod +x {k8s_script_remote}; {k8s_script_remote} worker')

        log.info('Installed K8s on the cluster.')

        join_token_worker = self.k8s_join_token(inventory.manager)
        join_token_manager = f'{join_token_worker} --control-plane'

        if inventory.workers:
            log.info('Join K8s workers.')
            for worker_name in inventory.workers:
                log.info(f'Join {worker_name} to K8s cluster.')
                machine.ssh(worker_name, f'sudo {join_token_worker}')
        else:
            log.info('No workers to join K8s cluster.')

        # Get kubectl config from manager.
        log.info('Get kubectl config from manager.')
        kube_config_file = '/tmp/kube-config'
        machine.scp(f'{inventory.manager}:~/.kube/config', kube_config_file)
        with open(kube_config_file) as fh:
            config = fh.read()
        try:
            os.unlink(kube_config_file)
        except:
            pass

        return {'join_tokens':
                    {'manager': join_token_manager,
                     'worker': join_token_worker},
                'config': config,
                'kind': 'k8s'}

    def _start_cluster(self, nodes: list, inventory: Inventory):
        cmd_xargs, env = self.docker_machine_args_and_env()

        # Provision VMs on CSP and install Docker Swarm.
        inputs = []
        for machine_name in inventory.all():
            inputs.append({'driver_name': self.driver_name,
                           'machine_name': machine_name,
                           'cmd_xargs': cmd_xargs,
                           'env': env})
        pool = multiprocessing.Pool(processes=len(inventory.all()))
        try:
            err_codes = pool.map(self._start_machine, inputs)
            pool.close()
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

        # Initialize Docker Swarm on manager.
        self.swarm_init(inventory)
        log.info('Swarm initialised on manager.')
        join_token_worker = f'sudo {self.swarm_join_token_worker(inventory)}'
        join_token_manager = f'sudo {self.swarm_join_token_manager(inventory)}'
        log.debug(f'Obtained cluster join tokens from {inventory.manager}')

        # Join workers to the cluster, if any.
        join_tokens_and_config = {}
        if inventory.workers:
            if not join_token_worker:
                raise Exception(f'Failed to get swarm join token from {inventory.manager}')
            inputs = []
            for worker_name in inventory.workers:
                inputs.append({'worker_name': worker_name,
                               'swarm_join_token': join_token_worker})
            pool = multiprocessing.Pool(processes=len(inventory.workers))
            try:
                log.info(f'Joining workers to cluster.')
                joined = pool.map(self.swarm_join, inputs)
                pool.close()
                log.info(f'Joined workers to cluster.')
            except Exception as ex:
                log.error(f'Failed to join workers to cluster: {ex}')
                pool.terminate()
                raise ex
            join_tokens_and_config = \
                {'join_tokens':
                     {'manager': join_token_manager,
                      'worker': join_token_worker},
                 'config': {},
                 'kind': 'swarm'}

        if self.coe_type.lower() == 'kubernetes':
            # Kubernetes supercedes Swarm join tokens.
            join_tokens_and_config = self.kubernetes_install(inventory)

        return join_tokens_and_config

    @should_connect
    def start(self, cluster_params: dict):
        multiplicity = cluster_params.get('multiplicity', 1)
        inventory = Inventory(self.machine_base_name, multiplicity=multiplicity)

        nodes = []
        try:
            msg = f'{self.coe_type.title()} cluster of size {multiplicity} on {self.driver_name}'
            log.info(f'Starting COE {msg}.')
            self._start_cluster(nodes, inventory)
            log.info(f'Started COE {msg}.')
            log.info(f'COE cluster: {self.list()}')
        except Exception as ex:
            log.error(f'COE cluster failed to start: {ex}')
            self.clear_connection()
            if len(nodes) > 0:
                self.stop(nodes=nodes)
            raise ex
        # TODO: Need to return join tokens and K8s config.
        return self._coe_credentials(inventory.manager),\
               self._coe_endpoint(inventory.manager),\
               nodes

    @staticmethod
    def _stop_node(node):
        node_name = node["node-name"]
        log.info(f'Stopping node: {node_name}')
        machine_folder = os.path.join(DOCKER_MACHINE_FOLDER, node_name)
        os.makedirs(machine_folder)
        with open(os.path.join(machine_folder, 'config.json'), 'w') as cfg:
            cfg.write(base64.b64decode(
                node["node-config-base64"].encode('ascii')).decode('ascii'))
        res = machine.rm(machine=node_name, force=True)
        log.info(f'Stopped node: {node_name}')
        return res

    @should_connect
    def stop(self, **kwargs):
        n = len(kwargs['nodes'])
        log.info(f'Stopping {n} nodes...')
        pool = multiprocessing.Pool(processes=n)
        stopped = pool.map(self._stop_node, kwargs['nodes'])
        pool.close()
        log.info(f'Stopped {sum(stopped)} out of {n} nodes ...')
        return stopped

    def list(self):
        return self.machine.ls()
