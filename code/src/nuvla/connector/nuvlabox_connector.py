# -*- coding: utf-8 -*-

import requests
import logging
import docker
import json
import re
import time
from .connector import Connector, should_connect
from .utils import create_tmp_file, timeout


class ClusterOperationNotAllowed(Exception):
    pass


class NuvlaBoxConnector(Connector):
    def __init__(self, **kwargs):
        super(NuvlaBoxConnector, self).__init__(**kwargs)

        self.api = kwargs.get("api")
        self.job = kwargs.get("job")
        self.ssl_file = None
        self.docker_client = None
        self.docker_api_endpoint = None
        self.nuvlabox_api = requests.Session()
        self.nuvlabox_api.verify = False
        self.nuvlabox_api.headers = {'Content-Type': 'application/json',
                                     'Accept': 'application/json'}

        self.nuvlabox_id = kwargs.get("nuvlabox_id")
        self.nuvlabox_resource = None
        self.nuvlabox = None
        self.nuvlabox_status = None
        self.nb_api_endpoint = None
        self.installer_base_name = 'nuvlabox/installer'
        self.installer_image_name = None
        self.timeout = 60
        self.acl = None
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'nuvlabox'

    def create_nuvlaboxes(self, number_of_nbs, vpn_server_id, basename="nuvlabox-conector-job", version=2, share_with=[]):
        nuvlabox_ids = []
        for count in range(1, number_of_nbs+1):
            nuvlabox_body = {
                'name': f'{basename}-{count}',
                'description': f'Automatically created by {self.connector_type} connector in Nuvla',
                'version': version
            }
            if vpn_server_id:
                nuvlabox_body['vpn-server-id'] = vpn_server_id
            r = self.api.add('nuvlabox', nuvlabox_body).data

            nb_id = r.get('resource-id')
            if share_with:
                # nb = self.api.get(nb_id).data
                # new_view_data = nb['acl'].get('view-data', []) + share_with

                self.api.edit(nb_id, {'acl': {'owners': ['group/scale-tests'], 'view-data': share_with}})
            nuvlabox_ids.append(nb_id)

        return nuvlabox_ids

    def build_cmd_line(self, list_cmd):
        return ['docker', '-H', self.docker_api_endpoint.replace('https://', '').replace('http://', ''),
                '--tls', '--tlscert', self.cert_file.name, '--tlskey', self.key_file.name,
                '--tlscacert', self.cert_file.name] + list_cmd

    def get_nuvlabox_status(self):
        self.nuvlabox_status = self.api.get(self.nuvlabox.get("nuvlabox-status")).data

    def get_credential(self):
        infra_service_groups = self.api.search('infrastructure-service-group',
                                               filter='parent="{}"'.format(self.nuvlabox.get("id")),
                                               select='id').resources

        cred_subtype = "infrastructure-service-swarm"

        for infra_service_group in infra_service_groups:

            infra_service_group_id = infra_service_group.id

            isg = self.api.get(infra_service_group_id).data

            service_hrefs = isg.get('infrastructure-services')
            for service_href in service_hrefs:
                service_id = service_href.get('href')
                infra_service = self.api.get(service_id).data
                if infra_service.get("subtype") == 'swarm':
                    credentials = self.api.search('credential',
                                                  filter='parent="{}" and subtype="{}"'.format(
                                                      service_id,
                                                      cred_subtype)).resources

                    return credentials[0].data, infra_service.get("endpoint")

    def setup_ssl_credentials(self):
        try:
            credential, is_endpoint = self.get_credential()
        except TypeError:
            raise Exception('Error: could not find infrastructure service credential for this NuvlaBox')

        try:
            secret = credential['cert'] + '\n' + credential['key']
        except KeyError:
            logging.error(
                "Credential for {} is either missing or incomplete".format(self.nuvlabox.get("id")))
            raise

        self.ssl_file = create_tmp_file(secret)
        self.cert_file = create_tmp_file(credential['cert'])
        self.key_file = create_tmp_file(credential['key'])
        self.nuvlabox_api.cert = self.ssl_file.name
        self.docker_api_endpoint = is_endpoint
        tls_config = docker.tls.TLSConfig(client_cert=(self.cert_file.name, self.key_file.name),
                                          verify=False,
                                          assert_hostname=False,
                                          assert_fingerprint=False)
        self.docker_client = docker.DockerClient(base_url=is_endpoint.replace('https://', '').replace('http://', ''),
                                                 tls=tls_config)

        return True

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        pass

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass

    def connect(self):
        logging.info('Connecting to NuvlaBox {}'.format(self.nuvlabox_id))
        self.nuvlabox_resource = self.api.get(self.nuvlabox_id)
        self.nuvlabox = self.nuvlabox_resource.data
        self.acl = self.nuvlabox.get('acl')
        self.get_nuvlabox_status()

        installer_tag = self.nuvlabox_status.get('nuvlabox-engine-version')
        self.installer_image_name = f'{self.installer_base_name}:{installer_tag}' if installer_tag \
            else f'{self.installer_base_name}:master'

        if self.job.get('execution-mode', '').lower() == 'pull':
            self.docker_client = docker.from_env()
        else:
            self.nb_api_endpoint = self.nuvlabox_status.get("nuvlabox-api-endpoint")
            if not self.nb_api_endpoint:
                msg = f'NuvlaBox {self.nuvlabox.get("id")} missing API endpoint in its status resource.'
                logging.warning(msg)

    def clear_connection(self, connect_result):
        if self.ssl_file:
            self.ssl_file.close()
            self.ssl_file = None
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def mgmt_api_request(self, endpoint, method, data, headers):
        self.setup_ssl_credentials()

        if isinstance(data, str):
            r = self.nuvlabox_api.request(method, endpoint, data=data, headers=headers,
                                          timeout=self.timeout)
        else:
            r = self.nuvlabox_api.request(method, endpoint, json=data, headers=headers,
                                          timeout=self.timeout)

        r.raise_for_status()
        r = r.json()

        return r

    @should_connect
    def nuvlabox_manage_ssh_key(self, action: str, pubkey: str):
        """
        Deletes an SSH key from the NuvlaBox

        :param pubkey: SSH public key string
        :param action: name of the action, as in the mgmt API endpoint
        :return:
        """

        self.job.set_progress(10)

        if self.nb_api_endpoint:
            action_endpoint = f'{self.nb_api_endpoint}/{action}'

            r = self.mgmt_api_request(action_endpoint, 'POST', pubkey, {"Content-Type": "text/plain"})
            self.job.set_progress(90)
        else:
            # running in pull, thus the docker socket is being shared
            user_home = self.nuvlabox_status.get('host-user-home')
            if not user_home:
                raise Exception(f'Cannot manage SSH keys unless the parameter host-user-home is set')

            if action.startswith('revoke'):
                cmd = "sh -c 'grep -v \"${SSH_PUB}\" %s > /tmp/temp && mv /tmp/temp %s && echo Success'" \
                      % (f'/rootfs/{user_home}/.ssh/authorized_keys', f'/rootfs/{user_home}/.ssh/authorized_keys')
            else:
                cmd = "sh -c 'echo -e \"${SSH_PUB}\" >> %s && echo Success'" \
                      % f'/rootfs/{user_home}/.ssh/authorized_keys'

            self.job.set_progress(90)

            r = docker.from_env().containers.run(
                'alpine',
                remove=True,
                command=cmd,
                environment={
                    'SSH_PUB': pubkey
                },
                volumes={
                    user_home: {
                        'bind': f'/rootfs/{user_home}'
                    }
                }
            )

            try:
                r = r.decode().rstrip()
            except AttributeError:
                pass

        self.job.set_progress(95)

        return r

    @should_connect
    def reboot(self):
        self.job.set_progress(10)
        if self.nb_api_endpoint:
            action_endpoint = f'{self.nb_api_endpoint}/reboot'

            r = self.mgmt_api_request(action_endpoint, 'POST', {}, None)
            self.job.set_progress(90)
        else:
            # running in pull, thus the docker socket is being shared
            cmd = "sh -c 'sleep 10 && echo b > /sysrq'"
            docker.from_env().containers.run('alpine',
                                             command=cmd,
                                             detach=True,
                                             remove=True,
                                             volumes={
                                                 '/proc/sysrq-trigger': {
                                                     'bind': '/sysrq'
                                                 }
                                             }
                                             )
            r = 'Reboot ongoing'

        return r

    @should_connect
    def start(self, **kwargs):
        """
        This method is being kept as a generic Mgmt API function, for backward compatibility with NB v1

        :param kwargs:
        :return:
        """
        self.job.set_progress(10)

        if self.nb_api_endpoint:
            self.job.set_progress(50)
        else:
            msg = "NuvlaBox {} missing API endpoint in its status resource".format(self.nuvlabox.get("id"))
            logging.warning(msg)
            raise Exception(msg)

        action_endpoint = '{}/{}'.format(self.nb_api_endpoint,
                                         kwargs.get('api_action_name', '')).rstrip('/')

        method = kwargs.get('method', 'GET').upper()
        payload = kwargs.get('payload', {})
        headers = kwargs.get('headers', None)

        r = self.mgmt_api_request(action_endpoint, method, payload, headers)

        self.job.set_progress(90)

        return r

    @should_connect
    def stop(self, **kwargs):
        pass

    def pull_docker_image(self, image_name, fallback_image_name=None):
        try:
            self.infer_docker_client().images.pull(image_name)
        except (docker.errors.ImageNotFound, docker.errors.NotFound):
            if fallback_image_name:
                logging.warning(f'Cannot pull image {image_name}')
                image_name = fallback_image_name
                logging.info(f'Trying operation with image {image_name}')
                self.infer_docker_client().images.pull(image_name)
            else:
                raise

        return image_name

    def infer_docker_client(self):
        dc = docker.from_env() if self.job.get('execution-mode', '') == 'pull' else self.docker_client
        return dc

    def run_container_from_installer(self, image, detach, container_name, volumes, command, container_env):
        try:
            self.infer_docker_client().containers.run(image,
                                                      detach=detach,
                                                      name=container_name,
                                                      volumes=volumes,
                                                      environment=container_env,
                                                      command=command)
        except docker.errors.NotFound as e:
            raise Exception(f'Unable to reach NuvlaBox Docker API: {str(e)}')
        except docker.errors.APIError as e:
            if '409' in str(e) and container_name in str(e):
                try:
                    existing = self.infer_docker_client().containers.get(container_name)
                    if existing.status.lower() != 'running':
                        logging.info(f'Deleting old {container_name} container because its status is {existing.status}')
                        existing.remove(force=True)
                        self.run_container_from_installer(image, detach, container_name, volumes, command)
                except Exception as ee:
                    raise Exception(f'Operation is already taking place and could not stop it: {str(e)} | {str(ee)}')
            else:
                raise

    def wait_for_container_output(self, container_name, timeout_after):
        exit_code = 0
        result = ''
        try:
            with timeout(timeout_after):
                tries = 0
                logging.info(f'Waiting {timeout_after} sec for NuvlaBox operation to finish...')
                while True:
                    if tries > 3:
                        raise Exception(f'Lost connection with the NuvlaBox Docker API at {self.docker_api_endpoint}')
                    try:
                        this_container = self.infer_docker_client().containers.get(container_name)
                        if this_container.status == 'exited':
                            # trick to get rid of bash ASCII chars
                            try:
                                result += re.sub(r'\[.*?;.*?m', '\n', this_container.logs().decode())
                            except:
                                result += this_container.logs().decode()
                            exit_code = this_container.wait().get('StatusCode', 0)
                            break
                    except requests.exceptions.ConnectionError:
                        # the compute-api might be being recreated...keep trying
                        tries += 1
                        time.sleep(5)
                    time.sleep(1)
        except TimeoutError:
            raise Exception(f'NuvlaBox operation timed out after {timeout_after} sec. Operation is incomplete!')
        finally:
            self.infer_docker_client().api.remove_container(container_name, force=True)

        return result, exit_code

    def assert_clustering_operation(self, action: str):
        """
        Double checks if the clustering operation can go on. For example, trying to join an existing cluster is
        only possible if the affected NuvlaBox has no active deployments

        :param action: clustering action
        :return: ID of cluster to delete, in case there's need
        """

        if action.lower().startswith("join"):
            # joining is only possible if not deployments are active on the NB
            active_deployments = self.api.search('deployment',
                                                 filter=f'nuvlabox="{self.nuvlabox_id}" and state!="STOPPED"').resources

            if len(active_deployments) > 0:
                raise ClusterOperationNotAllowed(f"NuvlaBox {self.nuvlabox_id} "
                                                 f"has {len(active_deployments)} active deployments")
        elif action.lower() in ['leave', 'force-new-cluster']:
            current_cluster_filter = f'nuvlabox-managers="{self.nuvlabox_id}" or nuvlabox-workers="{self.nuvlabox_id}"'
            current_clusters = self.api.search('nuvlabox-cluster',
                                              filter=current_cluster_filter).resources

            delete_clusters = []
            for cl in current_clusters:
                nuvlaboxes = cl.data.get('nuvlabox-managers', []) + \
                             cl.data.get('nuvlabox-workers', [])
                if len(nuvlaboxes) == 1 and self.nuvlabox_id in nuvlaboxes:
                    delete_clusters.append(cl.id)

            if delete_clusters:
                return delete_clusters

        return None

    def delete_cluster(self, cluster_id: str):
        try:
            self.api.delete(cluster_id)
        except:
            # we can ignore as it shall be cleanup up later on by the daily cleanup job
            logging.exception(f'Cannot delete leftover NuvlaBox cluster {cluster_id}. Leaving it be')
            pass

    @should_connect
    def cluster_nuvlabox(self, **kwargs):
        self.job.set_progress(10)

        # 1st - get the NuvlaBox Compute API endpoint and credentials
        if self.job.get('execution-mode', '').lower() in ['mixed', 'push']:
            self.setup_ssl_credentials()

        # 1.1 - assert the conditions to run this operation
        cluster_params_from_payload = json.loads(self.job.get('payload', '{}'))
        cluster_action = cluster_params_from_payload.get('cluster-action')

        delete_cluster_ids = self.assert_clustering_operation(cluster_action)
        self.job.set_progress(50)

        # 2nd - set the Docker args
        logging.info('Preparing parameters for NuvlaBox clustering')

        detach = True
        # container name
        container_name = f'cluster-nuvlabox'

        # volumes
        volumes = {
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock',
                'mode': 'ro'
            }
        }

        # command
        # action
        command = ['cluster', '--quiet']

        # cluster-action
        cluster_action = cluster_params_from_payload.get('cluster-action')
        if not cluster_action:
            raise Exception(f'Cluster operations need a cluster action: {cluster_params_from_payload}')

        if cluster_action.startswith('join-'):
            token = cluster_params_from_payload.get('token')
            join_address = cluster_params_from_payload.get('nuvlabox-manager-status', {}).get('cluster-join-address')
            if not token or not join_address:
                raise Exception(f'Cluster join requires both a token and address: {cluster_params_from_payload}')

            command += [f'--{cluster_action}={token}', f'--join-address={join_address}']
        else:
            command.append(f'--{cluster_action}')

        # 3rd - run the Docker command
        image = self.pull_docker_image(self.installer_image_name, f'{self.installer_base_name}:master')
        logging.info(f'Running NuvlaBox clustering via container from {image}, with args {" ".join(command)}')

        self.run_container_from_installer(image, detach, container_name, volumes, command)

        # 4th - monitor the op, waiting for it to finish to capture the output
        timeout_after = 600     # 10 minutes
        result = f'[NuvlaBox cluster action {cluster_action}] '
        wait_result, exit_code = self.wait_for_container_output(container_name, timeout_after)
        result += wait_result

        self.job.set_progress(95)

        for cluster_id in delete_cluster_ids:
            self.delete_cluster(cluster_id)

        return result, exit_code

    @should_connect
    def update_nuvlabox_engine(self, **kwargs):
        self.job.set_progress(10)

        # 1st - get the NuvlaBox Compute API endpoint and credentials
        if self.job.get('execution-mode', '').lower() in ['mixed', 'push']:
            self.setup_ssl_credentials()

        self.job.set_progress(50)

        # 2nd - set the Docker args
        detach = True

        # container name
        container_name = f'installer'

        # volumes
        volumes = {
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock',
                'mode': 'ro'
            },
            '/': {
                'bind': '/rootfs',
                'mode': 'ro'
            }
        }

        # command
        # action
        command = ['update']

        # action args
        command.append('--quiet')

        install_params_from_payload = json.loads(self.job.get('payload', '{}'))

        install_params_from_nb_status = self.nuvlabox_status.get('installation-parameters', {})

        if not install_params_from_nb_status:
            mandatory_update_args = ['project-name', 'working-dir', 'config-files']
            mandatory_update_args.sort()
            payload_keys = list(install_params_from_payload.keys())
            payload_keys.sort()
            if mandatory_update_args != list(filter(lambda x: x in mandatory_update_args, payload_keys)):
                raise Exception(f'Installation parameters are required, '
                                f'but are not present in NuvlaBox status {self.nuvlabox_status.get("id")}, '
                                f'nor given via the operation payload attribute')

        working_dir = install_params_from_payload.get("working-dir", install_params_from_nb_status["working-dir"])
        command.append(f'--working-dir={working_dir}')
        volumes[working_dir] = {
            'bind': '/rootfs-working-dir',
            'mode': 'ro'
        }

        project_name = install_params_from_payload.get("project-name", install_params_from_nb_status["project-name"])
        command.append(f'--project={project_name}')

        config_files = install_params_from_payload.get("config-files", install_params_from_nb_status["config-files"])
        compose_files = ','.join(config_files)
        command.append(f'--compose-files={compose_files}')

        current_env = install_params_from_nb_status.get('environment', [])
        new_env = install_params_from_payload.get('environment', [])

        if current_env:
            command += [f'--current-environment={repr(",".join(current_env))}']

        if new_env:
            command += [f'--new-environment={repr(",".join(new_env))}']

        target_release = kwargs.get('target_release')
        command.append(f'--target-version={target_release}')

        if all(k in self.api.login_params for k in ['key', 'secret']):
            updater_env = {
                'NUVLABOX_API_KEY': self.api.login_params['key'],
                'NUVLABOX_API_SECRET': self.api.login_params['secret']
            }
        else:
            updater_env = {}

        # 3rd - run the Docker command

        logging.info(f'Running NuvlaBox update container {self.installer_image_name}')
        image = self.pull_docker_image(self.installer_image_name, f'{self.installer_base_name}:master')
        self.run_container_from_installer(image, detach, container_name, volumes, command, updater_env)

        # 4th - monitor the update, waiting for it to finish to capture the output
        timeout_after = 600     # 10 minutes
        result = f'[NuvlaBox Engine update to {target_release}] '
        wait_result, exit_code = self.wait_for_container_output(container_name, timeout_after)
        result += wait_result

        self.job.set_progress(95)

        return result, exit_code

    # @should_connect
    def update(self, payload, **kwargs):
        """ Updates the NuvlaBox resource with the provided payload
        :param payload: content to be updated in the NuvlaBox resource
        """

        if payload:
            self.api.edit(self.nuvlabox_id, payload)

        self.job.set_progress(100)

    # @should_connect
    def commission(self, payload, **kwargs):
        """ Updates the NuvlaBox resource with the provided payload
        :param payload: content to be updated in the NuvlaBox resource
        """

        if payload:
            self.api.operation(self.nuvlabox_resource, "commission", data=payload)

    def list(self):
        pass
