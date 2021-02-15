# -*- coding: utf-8 -*-

import requests
import logging
import docker
import re
import time
from .connector import Connector, should_connect
from .utils import execute_cmd, create_tmp_file, timeout


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
        self.timeout = 60
        self.acl = None
        self.cert_file = None
        self.key_file = None

    @property
    def connector_type(self):
        return 'nuvlabox'

    def build_cmd_line(self, list_cmd):
        return ['docker', '-H', self.docker_api_endpoint.replace('https://', '').replace('http://', ''),
                '--tls', '--tlscert', self.cert_file.name, '--tlskey', self.key_file.name,
                '--tlscacert', self.cert_file.name] + list_cmd

    def get_nuvlabox_status(self):
        return self.api.get(self.nuvlabox.get("nuvlabox-status")).data

    def get_nuvlabox_api_endpoint(self):
        nb_status = self.get_nuvlabox_status()

        return nb_status.get("nuvlabox-api-endpoint")

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
        credential, is_endpoint = self.get_credential()
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

    @should_connect
    def start(self, **kwargs):
        self.job.set_progress(10)

        # 1st - get the NuvlaBox Mgmt API endoint
        nb_api_endpoint = self.get_nuvlabox_api_endpoint()
        if nb_api_endpoint:
            self.job.set_progress(50)
        else:
            msg = "NuvlaBox {} missing API endpoint in its status resource".format(self.nuvlabox.get("id"))
            logging.warning(msg)
            raise Exception(msg)

        # 2nd - get the corresponding credential and prepare the SSL environment
        self.setup_ssl_credentials()

        self.job.set_progress(90)
        action_endpoint = '{}/{}'.format(nb_api_endpoint,
                                         kwargs.get('api_action_name', '')).rstrip('/')

        method = kwargs.get('method', 'GET').upper()
        payload = kwargs.get('payload', {})
        headers = kwargs.get('headers', None)

        # 3rd - make the request
        if isinstance(payload, str):
            r = self.nuvlabox_api.request(method, action_endpoint, data=payload, headers=headers,
                                          timeout=self.timeout)
        else:
            r = self.nuvlabox_api.request(method, action_endpoint, json=payload, headers=headers,
                                          timeout=self.timeout)

        r.raise_for_status()

        self.job.set_progress(95)

        return r.json()

    @should_connect
    def stop(self, **kwargs):
        pass

    @should_connect
    def update_nuvlabox_engine(self, **kwargs):
        self.job.set_progress(10)

        # 1st - get the NuvlaBox Compute API endpoint and credentials
        self.setup_ssl_credentials()

        self.job.set_progress(50)

        # 2nd - set the Docker args
        # image name
        logging.info('Preparing parameters for NuvlaBox update')
        image = 'nuvlabox/installer:master'
        detach = True

        # container name
        container_name = f'installer'

        # volumes
        volumes = {
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock',
                'mode': 'ro'
            },
            '/': {'bind': '/rootfs',
                  'mode': 'ro'}
        }

        # command
        # action
        command = ['update']

        # action args
        command.append('--quiet')

        nb_status = self.get_nuvlabox_status()
        if 'installation-parameters' not in nb_status:
            logging.warning(f'Installation parameters are required, but are not present in NuvlaBox status {nb_status.id}')

        installation_parameters = nb_status['installation-parameters']
        if installation_parameters.get('working-dir'):
            command.append(f'--working-dir={installation_parameters.get("working-dir")}')

        if installation_parameters.get('project-name'):
            command.append(f'--project={installation_parameters.get("project-name")}')

        if installation_parameters.get('config-files'):
            compose_files = ','.join(installation_parameters.get("config-files"))
            command.append(f'--compose-files={compose_files}')

        if installation_parameters.get('environment'):
            environment = ','.join(installation_parameters.get("environment"))
            command += [f'--current-environment={environment}', f'--new-environment={environment}']

        target_release = kwargs.get('target_release')
        command.append(f'--target-version={target_release}')

        # 3rd - run the Docker command
        logging.info(f'Running NuvlaBox update container {image}')
        self.docker_client.images.pull(image)
        try:
            self.docker_client.containers.run(image,
                                              detach=detach,
                                              name=container_name,
                                              volumes=volumes,
                                              command=command)
        except docker.errors.NotFound as e:
            raise Exception(f'Unable to reach NuvlaBox Docker API at {self.docker_api_endpoint}: {str(e)}')
        except docker.errors.APIError as e:
            if '409' in str(e) and container_name in str(e):
                raise Exception(f'A NuvlaBox update is already taking place. Please wait for it to finish.')
            else:
                raise

        # 4th - monitor the update, waiting for it to finish to capture the output
        timeout_after = 600     # 10 minutes
        try:
            result = f'[NuvlaBox Engine update to {target_release}] '
            exit_code = 0
            with timeout(timeout_after):
                tries = 0
                logging.info(f'Waiting {timeout_after} sec for NuvlaBox update operation to finish...')
                while True:
                    if tries > 3:
                        raise Exception(f'Lost connection with the NuvlaBox Docker API at {self.docker_api_endpoint}')
                    try:
                        this_container = self.docker_client.containers.get(container_name)
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
            raise Exception(f'NuvlaBox update timed out after {timeout_after} sec. Operation is incomplete!')
        finally:
            self.docker_client.api.remove_container(container_name, force=True)

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
