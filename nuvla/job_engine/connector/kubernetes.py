# -*- coding: utf-8 -*-
import json
import logging
import os
import tempfile
from datetime import datetime
from subprocess import CompletedProcess
from typing import List, Union
from abc import ABC

import re

from .helm_driver import Helm
from .k8s_driver import Kubernetes
from ..job.job import Job
from .connector import Connector, should_connect
from .utils import join_stderr_stdout

log = logging.getLogger('k8s_connector')
log.setLevel(logging.DEBUG)


NE_STATUS_COLLECTION = 'nuvlabox-status'


class OperationNotAllowed(Exception):
    pass


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return K8sAppMgmt(
        ca=api_credential.get('ca', '').replace("\\n", "\n"),
        cert=api_credential.get('cert', '').replace("\\n", "\n"),
        key=api_credential.get('key', '').replace("\\n", "\n"),
        endpoint=api_infrastructure_service.get('endpoint'))


class K8sAppMgmt(Connector, ABC):
    """Class providing application management functionalities on Kubernetes.
    """

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.k8s = Kubernetes(**kwargs)

    def connector_type(self):
        return self.k8s.connector_type

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    def start(self, **kwargs) -> [str, List[dict]]:
        env = kwargs['env']
        files = kwargs['files']
        manifest = kwargs['docker_compose']
        # This is the deployment ID.
        deployment_uuid = kwargs['name']
        registries_auth = kwargs['registries_auth']

        custom_namespaces = Kubernetes.get_all_namespaces_from_manifest(manifest)
        log.debug('Namespaces from manifest: %s', custom_namespaces)
        if len(custom_namespaces) > 1:
            msg = (f'Only single namespace allowed in manifest. Found:'
                   f' {custom_namespaces}')
            log.error(msg)
            raise ValueError(msg)
        if custom_namespaces:
            namespace = list(custom_namespaces)[0]
        else:
            namespace = deployment_uuid

        result = join_stderr_stdout(
            self.k8s.apply_manifest_with_context(manifest, namespace, env,
                                                 files, registries_auth))

        objects = self._get_k8s_objects(deployment_uuid)

        return result, objects

    update = start

    def stop(self, **kwargs) -> str:
        deployment_uuid = kwargs['name']

        # Delete the deployment UUID-based namespace and all resources in it.
        try:
            return join_stderr_stdout(self.k8s.delete_namespace(deployment_uuid))
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                log.warning(f'Namespace "{deployment_uuid}" not found.')
            else:
                raise ex

        # When the deployment UUID-based namespace wasn't found, we will
        # delete all the resources by deployment UUID label. We will not be
        # deleting the namespaces, but only the resources in them. This is
        # because the namespaces might have not been created by Nuvla.
        label = f'nuvla.deployment.uuid={deployment_uuid}'
        return join_stderr_stdout(self.k8s.delete_all_resources_by_label(label))

    def list(self, filters=None, namespace=None):
        return self.k8s.get_namespace_objects(namespace, filters)

    def version(self) -> dict:
        """Returns the Kubernetes server and client versions.
        """
        return self.k8s.version()

    def get_services(self, deployment_uuid: str, _, **kwargs) -> list:
        """
        Returns both K8s Services and Deployments by `deployment_uuid`.

        :param deployment_uuid: Deployment UUID
        :param _: this parameter is ignored.
        :param kwargs: this parameter is ignored.
        :return: list of dicts
        """
        return self._get_k8s_objects(deployment_uuid)

    def _get_k8s_objects(self, deployment_uuid):
        objects = ['deployments',
                   'services']
        return self.k8s.get_objects(deployment_uuid, objects)

    def log(self, component: str, since: datetime, lines: int,
            namespace='') -> str:
        return self.k8s.log(component, since, lines, namespace)


class K8sEdgeMgmt:

    NE_HELM_NAMESPACE = 'default'

    def __init__(self, job: Job):

        if not job.is_in_pull_mode:
            raise OperationNotAllowed(
                'NuvlaEdge management actions are only supported in pull mode.')

        self.job = job
        self.api = job.api

        self.nuvlabox_id = self.job['target-resource']['href']

        self._nuvlabox = None
        self._nuvlabox_status = None

        self.k8s = Kubernetes.from_path_to_k8s_creds(job.nuvlaedge_shared_path)
        self.k8s.state_debug()

        self.helm = Helm(job.nuvlaedge_shared_path)

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    @property
    def nuvlabox(self):
        if not self._nuvlabox:
            self._nuvlabox = self.api.get(self.nuvlabox_id).data
        return self._nuvlabox

    @property
    def nuvlabox_status(self):
        if not self._nuvlabox_status:
            nuvlabox_status_id = self.nuvlabox.get(NE_STATUS_COLLECTION)
            self._nuvlabox_status = self.api.get(nuvlabox_status_id).data
        return self._nuvlabox_status

    def _build_reboot_job(self) -> str:
        image_name = self.k8s.base_image
        log.debug('Using image for reboot Job: %s', image_name)

        sleep_value = 10
        job_name = "reboot-nuvlaedge"

        command = f"['sh', '-c', 'sleep {sleep_value} && echo b > /sysrq']"

        manifest = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
spec:
  ttlSecondsAfterFinished: 0
  template:
    spec:
      containers:
      - name: {job_name}
        image: {image_name}
        command: {command}
        volumeMounts:
        - name: reboot-vol
          mountPath: /sysrq
      volumes:
      - name: reboot-vol   
        hostPath:
          path: /proc/sysrq-trigger
      restartPolicy: Never
  backoffLimit: 0
"""
        return manifest

    @should_connect
    def reboot(self) -> str:
        """
        Reboots the host.

        Generates the Kubernetes Job with the command to reboot the host and
        launches it.
        """

        manifest = self._build_reboot_job()
        log.debug('Host reboot Job: %s', manifest)

        result = self.k8s.apply_manifest(manifest, self.k8s.namespace)
        log.debug('Host reboot Job launch result: %s', result)

        return 'Reboot ongoing'

    # FIXME: this can be extracted and used for both K8s and Docker.
    def _deployed_components(self) -> list:
        """Get the list of deployed components from the NuvlaEdge status.
        """

        log.info('Getting NuvlaEdge components from Nuvla API.')

        resources = \
            self.api.search(NE_STATUS_COLLECTION,
                            filter=f'parent="{self.nuvlabox_id}"').resources
        for resource in resources:
            log.debug('Nuvlabox status ID: %s', resource.id)
            nb_status_data = \
                self.api.get(resource.id, select=['components']).data
            if log.level == logging.DEBUG:
                log.debug('The nuvlabox-status data is: %s',
                          json.dumps(nb_status_data, indent=2))
            return nb_status_data.get('components', [])
        return []

    def check_multiple_nuvlaedges(self, helm_name):
        """
        Check if the deployment is part of a multiple NuvlaEdge deployments
        on the same COE.
        """
        # FIXME: Join helm.run_command and k8s.read_job_log.
        # FIXME: Be more surgical in getting SET_MULTIPLE.
        job_name = self.k8s.create_object_name('check-multiple-NEs')
        cmd = (f'helm status -n {self.NE_HELM_NAMESPACE} {helm_name} '
               f'--show-resources -o json')
        cmd_result = self.helm.run_command(cmd, job_name)

        if cmd_result.returncode == 0 and not cmd_result.stderr:
            helm_log_result = self.k8s.read_job_log(job_name)
            log.debug('Helm status result: %s', helm_log_result)
            if 'SET_MULTIPLE' in helm_log_result.stdout:
                result = 'This deployment is part of a multiple \
                    deployment. It is not envisaged to run \
                    updates in such a test environment. Will not proceed.'
                log.info(result)
                return result, 95

        return None, cmd_result.returncode

    def _get_project_name(self) -> str:
        return json.loads(self.job.get('payload', '{}'))['project-name']

    def update_nuvlabox_engine(self, **kwargs):
        """
        Updates a Kubernetes deployed NuvlaEdge.

        The update is done by running a Helm upgrade command.
        """

        target_release = kwargs.get('target_release')
        log.debug('Target release: %s', target_release)

        if not self.nuvlabox_status:
            result = 'The nuvlabox status could not be retrieved. Cannot proceed.'
            log.warning(result)
            return result, 99

        log.debug('NuvlaEdge status: %s', self.nuvlabox_status)

        # Check said deployment is running.
        job_name = self.k8s.create_object_name('helm-ver-check')
        helm_command = 'helm list -n default --no-headers -o json'
        job_result = self.helm.run_command(helm_command, job_name)
        if job_result.returncode != 0:
            result = f'The helm list command gave error: {job_result.stderr}'
            return result, job_result.returncode
        log.info('Helm list result stdout: %s', job_result.stdout)

        project_name = self._get_project_name()
        helm_log_result = self.k8s.read_job_log(job_name)
        if not self._check_project_name(helm_log_result, project_name):
            return f'Project name {project_name} does not match \
                between helm on NuvlaEdge and Nuvla', 97

        self.helm.repo_update()

        helm_update_job_name = self.k8s.create_object_name('helm-update')
        helm_update_cmd = self._helm_gen_update_cmd_repo(target_release)
        helm_update_result = self.helm.run_command(helm_update_cmd,
                                                   helm_update_job_name)
        log.info(f'Helm update result: {helm_update_result}')
        current_version = json.loads(
            self.job.get('payload', '{}'))['current-version']
        result = self._check_target_release(helm_log_result, target_release,
                                            current_version)
        result = result + "\n" + helm_update_result.stdout

        return result, helm_update_result.returncode

    def get_helm_project_name(self) -> Union[str, None]:
        """
        Get the helm project name from the payload to make sure it exists.
        """
        project_name = self._get_project_name()

        # check that helm knows about the project name
        job_name = self.k8s.create_object_name('helm-name-check')
        job_cmd = f'helm list -n default --no-headers | grep {project_name}'
        job_result = self.helm.run_command(job_cmd, job_name)
        log.info(f'Helm name check result:\n {job_result}')

        if job_result.returncode == 0 and not job_result.stderr:
            helm_job_log_result = self.k8s.read_job_log(job_name)
            if project_name in helm_job_log_result.stdout:
                log.info(f'Found helm name: {project_name}')
                return project_name
        return None

    def _helm_gen_update_cmd_repo(self, target_release):
        """
        Generate the helm command that will run the update
        target_release: the new chart version

        This version generates the command based on the nuvlaedge/nuvlaedge repository
        """

        helm_repository = 'nuvlaedge/nuvlaedge'

        install_params_from_payload = json.loads(self.job.get('payload', '{}'))
        log.debug('Installation params: %s', install_params_from_payload)

        modules = install_params_from_payload['config-files']
        for module in modules:
            log.debug('Found module: %s', module)

        project_name = install_params_from_payload['project-name']
        project_uuid = ''
        if 'nuvlaedge-' in project_name:
            log.debug(f"project name index : {len('nuvlaedge-')}")
            project_uuid = project_name[len('nuvlaedge-'):]
            log.debug(f'Found UUID : {project_uuid}')
        peripherals = self.get_helm_peripherals(modules)
        env_vars = self.get_env_vars_string(install_params_from_payload)
        working_dir = self.get_working_dir(install_params_from_payload)

        mandatory_args = f' --set HOME={working_dir} \
            --set NUVLAEDGE_UUID=nuvlabox/{project_uuid} \
            --set kubernetesNode=$HOST_NODE_NAME'

        vpn_client_cmd = ''

        if 'vpn-client' in self._deployed_components():
            vpn_client_cmd = ' --set vpnClient=true'

        helm_namespace = ' -n default'

        helm_update_cmd = f'helm upgrade {project_name} \
            {helm_repository} \
            {helm_namespace} \
            --version {target_release} \
            {mandatory_args} \
            {vpn_client_cmd} \
            {peripherals} \
            {env_vars}'

        log.info(f'NuvlaEdge Helm upgrade command: {helm_update_cmd}')

        return helm_update_cmd

    @staticmethod
    def get_working_dir(install_params_from_payload):
        """
        Parse the payload and return a formatted string of helm environment variables
        """
        working_dir = "/root"

        if install_params_from_payload['working-dir']:
            return install_params_from_payload['working-dir']
        # do we test that the working dir exists?

        return working_dir

    @staticmethod
    def get_env_vars_string(install_params_from_payload: dict):
        """
        Parse the payload and return a formatted string of helm environment variables
        """

        new_vars_string = ''
        env_pair_pattern = r"^\w+=\w+$"

        envs = install_params_from_payload['environment']
        for env_pair in envs:
            log.debug(f"Environment pair: {env_pair}")
            env_pair_mod = "".join(env_pair.split())
            re_result = re.match(env_pair_pattern, env_pair_mod)
            log.debug(f"Matching result: {re_result}")
            if re_result:
                new_vars_string = new_vars_string + " --set " + env_pair_mod
                log.debug(f"Current env var string: \n{new_vars_string}")

        log.info('Environment list arguments: %s', new_vars_string)

        return new_vars_string

    @staticmethod
    def _check_target_release(helm_log_result, target_release, current_version):
        """
        Check the status of the target release
        """

        message = f"chart version from {current_version} to {target_release}"
        if target_release not in helm_log_result.stdout:
            result = "Updating " + message
            log.info(result)
        else:
            result = "No change of " + message
            log.info(result)
        return result

    @staticmethod
    def _check_project_name(helm_log_result: CompletedProcess, project_name: str):
        """
        Check the status of the project name (namespace)
        """
        if project_name not in helm_log_result.stdout:
            log.info(
                f'Project namespace does not match between helm and nuvla {project_name}')
            return False

        return True

    @staticmethod
    def get_helm_peripherals(modules: list):
        """
        Generate the correct helm-specific strings for the update command
        """
        peripherals = ""

        possible_modules = ["USB", "Bluetooth", "GPU", "Modbus", "Network",
                            "security"]
        for module in modules:
            log.info(f"JSW: Current module -> {module}")
            for module_test in possible_modules:
                if module_test.lower() in module.lower():
                    if "security" not in module_test.lower():
                        peripherals = peripherals + " --set peripheralManager" \
                                      + module_test + "=true "
                    else:
                        peripherals = peripherals + " --set " + module_test.lower() + "=true "

        log.info("Found peripherals list: %s", peripherals)
        return peripherals

    def get_project_name(self) -> str:
        ne_statuses = \
            self.api.search(NE_STATUS_COLLECTION,
                            filter=f'parent="{self.nuvlabox_id}"',
                            select='installation-parameters').resources
        for ne_status in ne_statuses:
            nb_status_data = self.api.get(ne_status.id).data
            return nb_status_data['installation-parameters']['project-name']


class K8sSSHKey:
    """
    Class to handle SSH keys. Adding and revoking
    """

    def __init__(self, job: Job, **kwargs):
        if not job.is_in_pull_mode:
            raise ValueError('This action is only supported by pull mode')

        self.job = job
        self.api = job.api

        self.nuvlabox_resource = self.api.get(kwargs.get("nuvlabox_id"))

        self.k8s = Kubernetes.from_path_to_k8s_creds(job.nuvlaedge_shared_path)
        self.k8s.state_debug()

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, _):
        self.k8s.clear_connection(None)

    # FIXME: this needs to be extracted and used for both K8s and Docker.
    @staticmethod
    def _get_user_home(nuvlabox_status):
        """
        Get the user home directory

        Arguments:
        nuvlabox_status: object containing the status of the nuvlabox
        """
        user_home = nuvlabox_status.get('host-user-home')
        if not user_home:
            user_home = os.getenv('HOME')
            if not user_home:
                user_home = "/root"
                # this could be interesting point to e.g. create a generic user edge_login and add ssh key?
                logging.info('Attention: The user home has been set to: %s ',
                             user_home)
        return user_home

    # FIXME: pull this up into future parent class.
    @should_connect
    def commission(self, payload):
        """ Updates the NuvlaEdge resource with the provided payload
        :param payload: content to be updated in the NuvlaEdge resource
        """
        if payload:
            self.api.operation(self.nuvlabox_resource, 'commission',
                               data=payload)

    @should_connect
    def _ssh_key_add_revoke(self, action: str, pubkey: str, user_home: str):
        """
        Adds or revokes an SSH key.
        """

        log.debug('User home directory %s ', user_home)

        sleep_sec = 2
        mount_path = tempfile.gettempdir() + '/host-fs'
        ssh_dir_path = f'{mount_path}/.ssh'
        log.info('The SSH directory path is: %s', ssh_dir_path)
        os.makedirs(ssh_dir_path, exist_ok=True)
        authorized_keys_path = f'{ssh_dir_path}/authorized_keys'

        if action == self.ACTION_REVOKE:
            job_name = self.ACTION_REVOKE
            cmds = [f'grep -v "${{SSH_PUB}}" {authorized_keys_path} > /tmp/temp',
                    f'mv /tmp/temp {authorized_keys_path}',
                    'echo Success deleting public key']
        elif action == self.ACTION_ADD:
            job_name = self.ACTION_ADD
            cmds = [f'sleep {sleep_sec}',
                    f'echo -e "${{SSH_PUB}}" >> {authorized_keys_path}',
                    'echo Success adding public key']
        else:
            log.error('Action %s is not supported', action)
            return 1

        cmd = ' && '.join(cmds)
        command = f"['sh', '-c', '{cmd}']"
        log.debug('SSH keys update command: %s', command)

        image_name = self.k8s.base_image
        manifest = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
spec:
  ttlSecondsAfterFinished: 5
  template:
    spec:
      containers:
      - name: {job_name}
        image: {image_name}
        command: {command}
        env:
        - name: SSH_PUB
          value: {pubkey}
        volumeMounts:
        - name: ssh-key-vol
          mountPath: {mount_path}
      volumes:
      - name: ssh-key-vol   
        hostPath:
          path: {user_home}
      restartPolicy: Never
"""
        log.debug('SSH keys update Job: %s ', manifest)

        result = self.k8s.apply_manifest(manifest, self.k8s.namespace)
        log.debug('SSH key Job launch result: %s', result)

        self.k8s.wait_job_succeeded(job_name, namespace=self.k8s.namespace)

        return result

    ACTION_ADD = 'add-ssh-key'
    ACTION_REVOKE = 'revoke-ssh-key'

    def _update_results(self, credential_id: str, ssh_keys: list, action: str):
        """Update the list of credentials server side.

        Arguments:
            credential_id: the Nuvla ID of the credential
            ssh_keys: the list of ssh keys for the NuvlaEdge
            action: either add or revoke the ssh key
        """
        if action == self.ACTION_ADD:
            logging.debug('Adding credential ID: %s', credential_id)
            ssh_keys += [credential_id]
            job_message = 'SSH public key added successfully'
        elif action == self.ACTION_REVOKE:
            logging.debug('Deleting credential ID: %s', credential_id)
            try:
                ssh_keys.remove(credential_id)
                logging.debug('The SSH keys after removal : %s', ssh_keys)
            except ValueError:
                pass
            job_message = 'SSH public key revoked successfully'
        else:
            job_message = f'Action {action} is not supported'
            log.error(job_message)

        self.commission({'ssh-keys': ssh_keys})

        logging.debug('The ssh-keys update payload: %s', ssh_keys)
        self.job.update_job(status_message=json.dumps(job_message))

    def manage_ssh_key(self, action: str, pubkey: str, credential_id: str,
                       nuvlabox_id: str) -> int:
        """
        Adds or revokes an SSH key from a NuvlaEdge.

        Arguments:
            action: value can be: add or revoke
            pubkey: the ssh public key to be added or revoked
            credential_id: credential ID
            nuvlabox_id: NuvlaEdge ID
        """
        nuvlaedge = self.api.get(nuvlabox_id).data
        logging.debug('NuvlaEdge resource: %s', nuvlaedge)
        ssh_keys = nuvlaedge.get('ssh-keys', [])
        logging.debug('Current SSH keys credential IDs: %s', ssh_keys)
        logging.info('The credential being added/revoked: %s', credential_id)

        if action == self.ACTION_ADD:
            if credential_id in ssh_keys:
                log.debug(
                    'The credential ID to be added is already present: %s',
                    credential_id)
                self.job.update_job(
                    status_message=json.dumps('SSH public key already present'))
                return 1
        elif action == self.ACTION_REVOKE:
            if credential_id not in ssh_keys:
                msg = 'The credential ID to be revoked is not in the list'
                log.debug(
                    '%s: %s', msg, credential_id)
                self.job.update_job(status_message=msg)
                return 1
        else:
            msg = f'SSH keys management action {action} is not supported'
            log.error(msg)
            self.job.update_job(status_message=msg)
            return 1

        nuvlaedge_status = self.api.get(NE_STATUS_COLLECTION).data
        log.debug('NuvlaEdge status: %s', nuvlaedge_status)
        user_home = self._get_user_home(nuvlaedge_status)
        result = self._ssh_key_add_revoke(action, pubkey, user_home)

        if result.returncode == 0 and not result.stderr:
            self._update_results(credential_id, ssh_keys, action)
            return 0

        self.job.update_job(
            status_message='The SSH public key add/revoke has failed.')
        return 2


class K8sLogging:

    def __init__(self, job: Job):
        self.k8s = Kubernetes.from_path_to_k8s_creds(job.nuvlaedge_shared_path)
        self.k8s.state_debug()

    def log(self, component: str, since: str, lines: int, namespace='') -> str:
        """
        Get the logs for a specific component.

        :param component: the component for which to get the logs
        :param since: the timestamp from which to get the logs
        :param lines: the number of lines to return
        :param namespace:
        :return: the logs
        """
        return self.k8s.log(component, since, lines, namespace)
