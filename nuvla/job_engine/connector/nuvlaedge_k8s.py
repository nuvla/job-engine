import json
import logging
import os
import re
import tempfile

from nuvla.job_engine.connector.connector import Connector, should_connect
from nuvla.job_engine.connector.helm_driver import Helm
from nuvla.job_engine.connector.k8s_driver import Kubernetes
from nuvla.job_engine.connector.utils import execute_cmd
from nuvla.job_engine.job import Job

NE_STATUS_COLLECTION = 'nuvlabox-status'
NE_HOST_USER_HOME = '/root'

log = logging.getLogger('ne_mgmt_k8s')


# FIXME: this needs to be extracted and used for both K8s and Docker.
def _get_user_home(nuvlabox_status: dict) -> str:
    """
    Get the user home directory.

    Arguments:
    nuvlabox_status: object containing the status of the nuvlabox.
    """

    user_home = nuvlabox_status.get('host-user-home')
    if user_home:
        log.debug(f'User home was taken from NuvlaEdge status: {user_home}')
        return user_home

    user_home = os.getenv('HOME')
    if user_home:
        log.warning(f'User home was set from $HOME: {user_home}')
        return user_home

    log.warning(f'Default user home used: {NE_HOST_USER_HOME}')
    return NE_HOST_USER_HOME


class OperationNotAllowed(Exception):
    pass


class NuvlaEdgeMgmtK8s(Connector):

    NE_HELM_NAMESPACE = 'default'
    NE_HELM_CHARTNAME = 'nuvlaedge'
    NE_HELM_REPO = 'https://nuvlaedge.github.io/deployment'

    def __init__(self, job: Job, **kwargs):

        super().__init__(**kwargs)

        if not job.is_in_pull_mode:
            raise OperationNotAllowed(
                'NuvlaEdge management actions are only supported in pull mode.')

        self.job = job
        self.api = job.api

        self.nuvlabox_id = self.job['target-resource']['href']

        self._nuvlabox = None
        self._nuvlabox_status = None

        self.k8s = Kubernetes.from_path_to_k8s_creds(job.nuvlaedge_shared_path)
        log.debug(self.k8s)

        self.helm = Helm(job.nuvlaedge_shared_path)

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, connect_result):
        self.k8s.clear_connection(connect_result)

    @property
    def connector_type(self):
        return 'nuvlabox-kubernetes'

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

    #
    # Reboot NuvlaEdge.
    #

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

    #
    # Update NuvlaEdge.
    #

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

    def _project_name(self) -> str:
        return json.loads(self.job.get('payload', '{}'))['project-name']

    @should_connect
    def _get_target_node_name(self):
        node_selector_cmd = self.k8s.build_cmd_line(
            ['get', 'deployments.apps', 'agent', '-o',
             "jsonpath='{.spec.template.spec.nodeSelector.kubernetes\.io/hostname}'"])
        log.debug('Node selector command: %s', ' '.join(node_selector_cmd))
        cmd_res = execute_cmd(node_selector_cmd)
        if cmd_res.returncode != 0:
            msg = (f'Failed to find target node name. Error getting node '
                   f'selector: {cmd_res.stderr}')
            log.error(msg)
            raise Exception(msg)
        if not cmd_res.stdout:
            msg = 'Failed to find target node name. Empty node selector.'
            log.error(msg)
            raise Exception(msg)
        return cmd_res.stdout

    @staticmethod
    def _env_to_vars(envs: dict) -> list:
        """
        Parse the environment variables and convert them to helm --set vars.
        """

        env_pair_pattern = r'^\w+=\w+$'

        set_vars = []
        for env_pair in envs:
            log.debug('Environment pair: %s', env_pair)
            env_pair_mod = ''.join(env_pair.split())
            re_result = re.match(env_pair_pattern, env_pair_mod)
            log.debug('Matching result: %s', re_result)
            if re_result:
                set_vars.extend(['--set ', env_pair_mod])
                log.debug('Current env vars: %s', set_vars)

        log.info('Environment arguments: %s', set_vars)

        return set_vars

    @staticmethod
    def _extra_modules(modules: list) -> list:
        """
        Generate the correct helm-specific strings for the upgrade command
        """
        peripherals = []

        possible_modules = [
            'USB',
            'Bluetooth',
            'GPU',
            'Modbus',
            'Network',
            'security']

        for module in modules:
            for m in possible_modules:
                if m.lower() in module.lower():
                    if 'security' in m:
                        peripherals.extend(['--set', 'security=true'])
                    else:
                        peripherals.extend(
                            ['--set', f'peripheralManager{m}=true'])

        log.info('Found peripherals list: %s', peripherals)
        return peripherals

    def _build_helm_upgrade_cmd(self, target_release) -> list:
        """
        Generate the helm command that will run the update

        target_release: the new chart version
        """

        install_params = json.loads(self.job.get('payload', '{}'))
        log.debug('Installation params: %s', install_params)

        project_name = install_params['project-name']
        if not project_name:
            msg = 'Project name not provided. Cannot proceed.'
            log.error(msg)
            raise Exception(msg)

        cmd = [
            'upgrade',
            project_name,
            # FIXME: chart name and repo should be allowed to be overridden.
            self.NE_HELM_CHARTNAME,
            '--repo', self.NE_HELM_REPO,
            '-n', 'default',
            '--version', target_release]

        # Variables to be set in the helm command.
        ne_id = self.nuvlabox_status['parent']
        home_dir = _get_user_home(self.nuvlabox_status)
        target_node_name = self._get_target_node_name()
        cmd.extend([
            '--set', f'HOME={home_dir}',
            # FIXME: NUVLAEDGE_ID should be used instead of NUVLAEDGE_UUID.
            '--set', f'NUVLAEDGE_UUID={ne_id}',
            '--set', f'NUVLAEDGE_ID={ne_id}',
            '--set', f'NUVLA_ENDPOINT={self.api.endpoint}',
            '--set', f'NUVLA_ENDPOINT_INSECURE={not self.api.session.verify}',
            '--set', f'kubernetesNode={target_node_name}'])

        if 'vpn-client' in self._deployed_components():
            cmd.extend(['--set', 'vpnClient=true'])

        cmd.extend(
            self._extra_modules(install_params['config-files']))

        cmd.extend(
            self._env_to_vars(install_params['environment']))

        if any(param is None for param in cmd):
            msg = ('Some params of the helm command are not defined. Cannot '
                   'proceed. Params: %s' % cmd)
            log.error(msg)
            raise Exception(msg)

        log.info(f'NuvlaEdge Helm upgrade command: {" ".join(cmd)}')

        return cmd

    def update_nuvlabox_engine(self, **kwargs):
        """
        Updates NuvlaEdge deployed on Kubernetes.

        The update is done by running a Helm upgrade command.
        """

        target_release = kwargs.get('target_release')
        log.debug('Target release: %s', target_release)
        if not target_release:
            result = 'Target release not provided. Cannot proceed.'
            log.error(result)
            return result, 99

        if not self.nuvlabox_status:
            result = ('The NuvlaEdge status could not be retrieved. Cannot '
                      'proceed.')
            log.error(result)
            return result, 99

        log.debug('NuvlaEdge status: %s', self.nuvlabox_status)

        upgrade_cmd = self._build_helm_upgrade_cmd(target_release)
        upgrade_result = self.helm.run_command(upgrade_cmd)
        if upgrade_result.returncode != 0:
            log.error(f'NuvlaEdge update failed: {upgrade_result}')
            return upgrade_result.stderr, upgrade_result.returncode

        log.info(f'NuvlaEdge update successful: {upgrade_result}')

        current_version = json.loads(
            self.job.get('payload', '{}'))['current-version']
        result = \
            f'Updated from {current_version} to {target_release}\n' + \
            upgrade_result.stdout

        return result, upgrade_result.returncode


class NuvlaEdgeMgmtK8sSSHKey:
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
        log.debug(self.k8s)

    def connect(self):
        self.k8s.connect()

    def clear_connection(self, _):
        self.k8s.clear_connection(None)

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
        user_home = _get_user_home(nuvlaedge_status)
        result = self._ssh_key_add_revoke(action, pubkey, user_home)

        if result.returncode == 0 and not result.stderr:
            self._update_results(credential_id, ssh_keys, action)
            return 0

        self.job.update_job(
            status_message='The SSH public key add/revoke has failed.')
        return 2


class NuvlaEdgeMgmtK8sLogging:

    def __init__(self, ne_db: str):
        """
        :param ne_db: path to NuvlaEdge local filesystem database.
        """
        self.k8s = Kubernetes.from_path_to_k8s_creds(ne_db)
        log.debug(self.k8s)

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
