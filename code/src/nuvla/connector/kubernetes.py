# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
import tempfile
import time
import yaml
import random
import string
import uuid
import re

from datetime import datetime
from tempfile import TemporaryDirectory

from ..job.job import Job
from .connector import Connector, should_connect
from .utils import (create_tmp_file,
                    execute_cmd,
                    generate_registry_config,
                    join_stderr_stdout)


log = logging.getLogger('kubernetes')


class OperationNotAllowed(Exception):
    pass


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return Kubernetes(
        ca=api_credential.get('ca', '').replace("\\n", "\n"),
        cert=api_credential.get('cert', '').replace("\\n", "\n"),
        key=api_credential.get('key', '').replace("\\n", "\n"),
        endpoint=api_infrastructure_service.get('endpoint'))


def get_kubernetes_local_endpoint():
    kubernetes_host = os.getenv('KUBERNETES_SERVICE_HOST')
    kubernetes_port = os.getenv('KUBERNETES_SERVICE_PORT')
    if kubernetes_host and kubernetes_port:
        return f'https://{kubernetes_host}:{kubernetes_port}'
    return ''


class Kubernetes(Connector):

    def __init__(self, **kwargs):
        super(Kubernetes, self).__init__(**kwargs)
        # Mandatory kwargs
        self.ca = self.kwargs['ca']
        self.cert = self.kwargs['cert']
        self.key = self.kwargs['key']

        self.endpoint = self.kwargs['endpoint']
        self.ca_file = None
        self.cert_file = None
        self.key_file = None

        self.ne_image_registry = os.getenv('NE_IMAGE_REGISTRY', '')
        self.ne_image_org = os.getenv('NE_IMAGE_ORGANIZATION', 'sixsq')
        self.ne_image_repo = os.getenv('NE_IMAGE_REPOSITORY', 'nuvlaedge')
        self.ne_image_tag = os.getenv('NE_IMAGE_TAG', 'latest')
        self.ne_image_name = os.getenv('NE_IMAGE_NAME', f'{self.ne_image_org}/{self.ne_image_repo}')
        self.base_image = f'{self.ne_image_registry}{self.ne_image_name}:{self.ne_image_tag}'

    @property
    def connector_type(self):
        return 'Kubernetes-cli'

    def connect(self):
        log.info('Connecting to endpoint: %s', self.endpoint)
        self.ca_file = create_tmp_file(self.ca)
        self.cert_file = create_tmp_file(self.cert)
        self.key_file = create_tmp_file(self.key)

    def clear_connection(self, connect_result):
        if self.ca_file:
            self.ca_file.close()
            self.ca_file = None
        if self.cert_file:
            self.cert_file.close()
            self.cert_file = None
        if self.key_file:
            self.key_file.close()
            self.key_file = None

    def build_cmd_line(self, list_cmd):
        '''Build the kubectl command line

           arguments:
           list_cmd: a list containing the kubectl command line and arguments
        '''
        return ['kubectl', '-s', self.endpoint,
                '--client-certificate', self.cert_file.name,
                '--client-key', self.key_file.name,
                '--certificate-authority', self.ca_file.name] \
               + list_cmd

    @staticmethod
    def _create_deployment_context(directory_path, namespace, docker_compose,
                                   files, registries_auth):
        manifest_file_path = directory_path + '/manifest.yml'
        with open(manifest_file_path, 'w') as manifest_file:
            manifest_file.write(docker_compose)

        namespace_file_path = directory_path + '/namespace.yml'
        with open(namespace_file_path, 'w') as namespace_file:
            namespace_data = {'apiVersion': 'v1',
                              'kind': 'Namespace',
                              'metadata': {'name': namespace}}
            yaml.safe_dump(namespace_data, namespace_file, allow_unicode=True)

        kustomization_data = {'namespace': namespace,
                              'resources': ['manifest.yml', 'namespace.yml']}

        if files:
            for file_info in files:
                file_path = directory_path + "/" + file_info['file-name']
                f = open(file_path, 'w')
                f.write(file_info['file-content'])
                f.close()

        if registries_auth:
            config = generate_registry_config(registries_auth)
            config_b64 = base64.b64encode(config.encode('ascii')).decode(
                'utf-8')
            secret_registries_fn = 'secret-registries-credentials.yml'
            secret_registries_path = os.path.join(directory_path,
                                                  secret_registries_fn)
            with open(secret_registries_path, 'w') as secret_registries_file:
                secret_registries_data = {'apiVersion': 'v1',
                                          'kind': 'Secret',
                                          'metadata': {
                                              'name': 'registries-credentials'},
                                          'data': {
                                              '.dockerconfigjson': config_b64},
                                          'type': 'kubernetes.io/dockerconfigjson'}
                yaml.safe_dump(secret_registries_data, secret_registries_file,
                               allow_unicode=True)
            kustomization_data.setdefault('resources', []) \
                .append(secret_registries_fn)

        kustomization_file_path = directory_path + '/kustomization.yml'
        with open(kustomization_file_path, 'w') as kustomization_file:
            yaml.safe_dump(kustomization_data, kustomization_file,
                           allow_unicode=True)

    @should_connect
    def start(self, **kwargs):
        # Mandatory kwargs
        env = kwargs['env']
        files = kwargs['files']
        manifest = kwargs['docker_compose']
        namespace = kwargs['name']
        registries_auth = kwargs['registries_auth']

        envsubst_shell_format = ' '.join(['${}'.format(k) for k in env.keys()])
        cmd = ['envsubst', envsubst_shell_format]
        manifest_env_subs = execute_cmd(cmd,
                                        env=env,
                                        input=manifest).stdout

        with TemporaryDirectory() as tmp_dir_name:
            Kubernetes._create_deployment_context(tmp_dir_name,
                                                  namespace,
                                                  manifest_env_subs,
                                                  files,
                                                  registries_auth)

            cmd_deploy = self.build_cmd_line(['apply', '-k', tmp_dir_name])

            result = join_stderr_stdout(execute_cmd(cmd_deploy))

            services = self._get_services(namespace)

            return result, services

    update = start

    @should_connect
    def stop(self, **kwargs):
        namespace = kwargs['name']

        cmd_stop = self.build_cmd_line(['delete', 'namespace', namespace])

        try:
            return join_stderr_stdout(execute_cmd(cmd_stop))
        except Exception as ex:
            if 'NotFound' in ex.args[0] if len(ex.args) > 0 else '':
                return f'Namespace "{namespace}" not found.'
            else:
                raise ex

    @should_connect
    def list(self, filters=None):
        # FIXME: Implement.
        # cmd = self.build_cmd_line(['stack', 'ls'])
        # return execute_cmd(cmd)
        pass

    TIMESTAMP_FMT_UTC = '%Y-%m-%dT%H:%M:%S.%f000Z'

    @classmethod
    def _timestamp_now_utc(cls) -> str:
        time_now = datetime.timestamp(datetime.now())
        utc_timestamp = datetime.utcfromtimestamp(time_now)
        return utc_timestamp.strftime(cls.TIMESTAMP_FMT_UTC)

    def _build_logs_cmd(self,
                        namespace: str,
                        pod_unique_id: str,
                        container_name: str,
                        since: datetime,
                        tail_lines: int) -> list:

        container_opts = [f'pod/{pod_unique_id}',
                          f'--container={container_name}']

        list_opts_log = ['--timestamps=true',
                         '--tail', str(tail_lines),
                         '--namespace', namespace]
        if since:
            list_opts_log.extend(['--since-time', since.isoformat()])

        return self.build_cmd_line(['logs'] + container_opts + list_opts_log)

    @should_connect
    def _get_container_logs(self,
                            namespace,
                            pod: dict,
                            since: datetime,
                            tail_lines: int = 10) -> str:
        """
        Given `pod` definition in a `namespace`, returns `tail_lines` log lines
        from `since` date per each container found in the `pod` .

        :param namespace: str
        :param pod: dict
        :param since: datetime
        :param tail_lines: int
        :return: str
        """
        pod_logs = ''
        pod_unique_id = pod['metadata']['name']
        log.debug('Working with pod: %s', pod_unique_id)

        for container in pod['spec']['containers']:
            container_name = container['name']
            log.debug('Working with container: %s', container_name)

            cmd = self._build_logs_cmd(namespace,
                                       pod_unique_id,
                                       container_name,
                                       since,
                                       tail_lines)
            log.debug('Logs command line: %s', cmd)

            pod_container = f'pod/{pod_unique_id}->{container_name}'

            try:
                container_logs = execute_cmd(cmd).stdout
            except Exception as ex:
                log.error('Failed getting logs from %s: %s', pod_container, ex)
                continue

            if container_logs:
                pod_logs += \
                    f'\nLog last {tail_lines} lines for container ' \
                    f'{pod_container}' \
                    f'\n{container_logs}'
            else:
                pod_logs += \
                    f'\n{self._timestamp_now_utc()}' \
                    f' There are no log entries for {pod_container}' \
                    f' since {since.isoformat()}'
        return pod_logs

    def _get_pods_logs(self,
                       namespace,
                       pods: list,
                       since: datetime,
                       num_lines: int) -> str:

        logs_strings = []
        for pod in pods:
            log.debug('Get logs from pod: %s', pod)
            if pod["kind"] == 'Pod':
                logs = self._get_container_logs(namespace,
                                                pod,
                                                since,
                                                num_lines)
                logs_strings.append(logs)

        log.debug('Final log string: %s', logs_strings)

        return '\n'.join(logs_strings)

    @staticmethod
    def _filter_objects_owned(objects: list,
                              kind: str,
                              owner_kind: str,
                              owner_name: str) -> list:
        """
        Given list of `objects` and desired object `kind`, returns list of
        the object kinds that are owned by the object with kind `owner_kind`
        and name `owner_name`.

        :param objects: list
        :param kind: str
        :param owner_kind: str
        :param owner_name: str
        :return: list
        """
        component_pods = []
        for obj in objects:
            if obj['kind'] == kind and 'ownerReferences' in obj['metadata']:
                owner = obj['metadata']['ownerReferences'][0]
                if owner_kind == owner['kind'] and owner_name == owner['name']:
                    component_pods.append(obj)
        return component_pods

    def _exec_stdout_json(self, cmd_params) -> {}:
        cmd = self.build_cmd_line(cmd_params)
        cmd_stdout = execute_cmd(cmd).stdout
        return json.loads(cmd_stdout)

    @should_connect
    def _get_pods_cronjob(self, namespace, obj_name) -> list:
        # Find Jobs associated with the CronJob and get its name.
        kind_top_level = 'CronJob'
        pods_owner_kind = 'Job'
        jobs = self._exec_stdout_json(['get', pods_owner_kind,
                                       '-o', 'json',
                                       '--namespace', namespace])
        jobs_owned_by_cronjob = self._filter_objects_owned(jobs.get('items', []),
                                                           pods_owner_kind,
                                                           kind_top_level,
                                                           obj_name)
        if len(jobs_owned_by_cronjob) < 1:
            log.error(f'Failed to find {pods_owner_kind} owned by '
                      f'{kind_top_level}/{obj_name}.')
            return []

        jobs_names = [x['metadata']['name'] for x in jobs_owned_by_cronjob]

        # Find Pods owned by the Jobs.
        pods = []
        all_pods = self._exec_stdout_json(['get', 'pods',
                                           '-o', 'json',
                                           '--namespace', namespace])
        for pods_owner_name in jobs_names:
            res = self._filter_objects_owned(all_pods['items'],
                                             'Pod', pods_owner_kind, pods_owner_name)
            pods.extend(res)
        return pods

    @should_connect
    def _get_pods_deployment(self, namespace, obj_name) -> list:
        # Find ReplicaSet associated with the Deployment and get its name.
        kind_top_level = 'Deployment'
        pods_owner_kind = 'ReplicaSet'
        replicasets = self._exec_stdout_json(['get', pods_owner_kind,
                                              '-o', 'json',
                                              '--namespace', namespace])
        kinds_second_level = self._filter_objects_owned(
            replicasets.get('items', []),
            pods_owner_kind,
            kind_top_level,
            obj_name)
        if len(kinds_second_level) < 1:
            log.error(f'Failed to find {pods_owner_kind} owned by '
                      f'{kind_top_level}/{obj_name}.')
            return []
        if len(kinds_second_level) > 1:
            msg = f'There can only be single {pods_owner_kind}. ' \
                  f'Found: {kinds_second_level}'
            log.error(msg)
            raise Exception(msg)
        pods_owner_name = kinds_second_level[0]['metadata']['name']
        # Find Pods owned by the ReplicaSet.
        all_pods = self._exec_stdout_json(['get', 'pods',
                                           '-o', 'json',
                                           '--namespace', namespace])
        return self._filter_objects_owned(all_pods['items'], 'Pod',
                                          pods_owner_kind, pods_owner_name)

    @should_connect
    def _get_pods_regular(self, namespace, owner_kind, owner_name):
        kind = 'Pod'
        all_pods = self._exec_stdout_json(['get', kind,
                                           '-o', 'json',
                                           '--namespace', namespace])
        if len(all_pods) < 1:
            log.warning(f'No {kind} in namespace {namespace}.')
            return []
        return self._filter_objects_owned(all_pods['items'], kind,
                                          owner_kind, owner_name)

    def _get_pods(self, namespace, obj_kind, obj_name) -> list:
        if 'Deployment' == obj_kind:
            return self._get_pods_deployment(namespace, obj_name)

        if 'CronJob' == obj_kind:
            return self._get_pods_cronjob(namespace, obj_name)

        if obj_kind in ['Job', 'DaemonSet', 'StatefulSet']:
            return self._get_pods_regular(namespace, obj_kind, obj_name)

    def _get_component_logs(self,
                            namespace: str,
                            obj_kind: str,
                            obj_name: str,
                            since: datetime,
                            num_lines: int) -> str:
        """
        Given Kubernetes workload object kind `obj_kind` and name `obj_name`
        running in `namespace`, returns max `num_lines` logs from `since` of all
        containers running in all its pods.

        :param namespace: str - namespace component is running in
        :param obj_kind: str - K8s object kind (e.g. Deployment, Job, etc.)
        :param obj_name: str - K8s object name (e.g. nginx)
        :param since: datetime - from what time to collect the logs
        :param num_lines: int - max number of log lines to collect
        :return: str - logs as string
        """
        pods = self._get_pods(namespace, obj_kind, obj_name)
        try:
            return self._get_pods_logs(namespace, pods, since, num_lines)
        except Exception as ex:
            log.error('Problem getting logs string: %s ', ex)
        return ''

    WORKLOAD_OBJECT_KINDS = \
        ['Deployment',
         'Job',
         'CronJob',
         'StatefulSet',
         'DaemonSet']

    @should_connect
    def log(self, component: str, since: datetime, num_lines: int, **kwargs) -> str:
        """
        Given `component` as `<K8s object kind>/<name>` (e.g. Deployment/nginx),
        returns logs of all the containers of all the pods belonging to the
        `component` (as sting).

        Only Kubernetes workload object kinds (which actually can contain Pods)
        are considered for collection of logs.

        :param component: str - `<K8s object kind>/<name>` (e.g. Deployment/nginx)
        :param since: datetime - from what time to collect the logs
        :param num_lines: int - max number of log lines to collect
        :param kwargs: optional parameters
        :return: str - logs as string
        """

        obj_kind, obj_name = component.split('/')
        if obj_kind not in self.WORKLOAD_OBJECT_KINDS:
            msg = f"There are no meaningful logs for '{obj_kind}'."
            log.warning(msg)
            return f'{self._timestamp_now_utc()} {msg}\n'

        try:
            log.info('Getting logs for: %s', component)
            return self._get_component_logs(kwargs['namespace'], obj_kind,
                                            obj_name, since, num_lines)
        except Exception as ex:
            msg = f'There was an error getting logs for: {component}'
            log.error('%s: %s', msg, ex)
            return f'{self._timestamp_now_utc()} {msg}\n'

    @staticmethod
    def _extract_service_info(kube_resource):
        resource_kind = kube_resource['kind']
        node_id = '.'.join([resource_kind,
                            kube_resource['metadata']['name']])
        service_info = {'node-id': node_id}
        if resource_kind == 'Deployment':
            replicas_desired = kube_resource['spec']['replicas']
            replicas_running = kube_resource['status'].get('readyReplicas', 0)
            service_info['replicas.desired'] = str(replicas_desired)
            service_info['replicas.running'] = str(replicas_running)
        if resource_kind == 'Service':
            ports = kube_resource['spec']['ports']
            for port in ports:
                external_port = port.get('nodePort')
                if external_port:
                    internal_port = port['port']
                    protocol = port['protocol'].lower()
                    service_info[f'{protocol}.{internal_port}'] = str(
                        external_port)
        return service_info

    def _get_services(self, namespace):
        cmd_services = self.build_cmd_line(['get', 'services', '--namespace',
                                            namespace, '-o', 'json'])
        kube_services = json.loads(execute_cmd(cmd_services).stdout).get(
            'items', [])

        cmd_deployments = self.build_cmd_line(
            ['get', 'deployments', '--namespace',
             namespace, '-o', 'json'])
        kube_deployments = json.loads(execute_cmd(cmd_deployments).stdout).get(
            'items', [])

        services = [Kubernetes._extract_service_info(kube_resource)
                    for kube_resource in kube_services + kube_deployments]

        return services

    @should_connect
    def version(self):
        cmd = self.build_cmd_line(['version', '-o', 'json'])
        version = execute_cmd(cmd, timeout=5).stdout
        return json.loads(version)

    @should_connect
    def get_services(self, name, env, **kwargs):
        return self._get_services(name)
    
    # @should_connect
    def commission(self, payload):
        """ Updates the NuvlaEdge resource with the provided payload
        :param payload: content to be updated in the NuvlaEdge resource
        """
        # pass
        if payload:
            self.api.operation(self.nuvlabox_resource, "commission", data=payload)


class K8sEdgeMgmt(Kubernetes):

    def __init__(self, job: Job, **kwargs):

        self.job = job
        self.api = job.api

        if not job.is_in_pull_mode:
            raise OperationNotAllowed(
                'NuvlaEdge management actions are only supported in pull mode.')

        # FIXME: This needs to be parameterised.
        path = '/srv/nuvlaedge/shared'
        super(K8sEdgeMgmt, self).__init__(
            ca=open(f'{path}/ca.pem', encoding="utf8").read(),
            key=open(f'{path}/key.pem', encoding="utf8").read(),
            cert=open(f'{path}/cert.pem', encoding="utf8").read(),
            endpoint=get_kubernetes_local_endpoint()
        )
    
    def KUB_JOB(self):
        return 'job.batch/'

    @should_connect
    def reboot(self):
        """
        Function to generate the kubernetes reboot manifest and execute the job
        """
        log.info(f'Using image: {self.base_image}')

        sleep_value = 10
        image_name = self.base_image
        the_job_name = "reboot-nuvlaedge"

        cmd = f"sleep {sleep_value} && echo b > /sysrq"
        command = f"['sh', '-c', '{cmd}' ]"

        reboot_yaml_manifest = f"""
            apiVersion: batch/v1
            kind: Job
            metadata:
              name: {the_job_name}
            spec:
              ttlSecondsAfterFinished: 0
              template:
                spec:
                  containers:
                  - name: {the_job_name}
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

        ## log.debug(f"The generated command is: {built_command}")
        log.debug(f"The re-formatted YAML is: \n{reboot_yaml_manifest}")

        with TemporaryDirectory() as tmp_dir_name:
            filename = f'{tmp_dir_name}/reboot_job_manifest.yaml'
            with open(filename, 'w', encoding="utf-8") as reboot_manifest_file:
                reboot_manifest_file.write(reboot_yaml_manifest)

            cmd = ['apply', '-f', filename]
            kubectl_cmd_reboot = self.build_cmd_line(cmd)

            reboot_result = execute_cmd(kubectl_cmd_reboot)
            log.debug(f'The result of the ssh key addition: {reboot_result}')
        return reboot_result

    def update_nuvlabox_engine(self, **kwargs):
        """
        General method to update a kubernetes deployed NuvlaEdge
        """

        target_release = kwargs.get('target_release')
        log.debug(f'Target release: {target_release}')

        the_job_name = self.create_job_name("helm-ver-check")
        helm_command = "'helm list -n default --no-headers'"
        helm_version_result = self.run_helm_container(the_job_name, helm_command)

        if helm_version_result.returncode == 0 and not helm_version_result.stderr:
            helm_log_result = self.read_a_log_file(the_job_name)
            current_version = json.loads(self.job.get('payload', '{}'))['current-version']
            project_name = json.loads(self.job.get('payload', '{}'))['project-name']
            result = self.check_target_release(helm_log_result, target_release, current_version) # no bother
            if not self.check_project_name(helm_log_result, project_name):
                return \
                    "Project name does not match between helm on NulvaEdge and nuvla.io %s"\
                        %(f'{project_name}'), 99
            helm_update_job_name = self.create_job_name("helm-update")
            helm_update_cmd = self.helm_generate_update_command(target_release)
            helm_update_result = self.run_helm_container(helm_update_job_name, helm_update_cmd)
            log.info(f"Helm update result:\n {helm_update_result}")
            result = result + "\n" + helm_update_result.stdout
        else:
            result = "The helm version command gave error \n %s"%(f'{helm_version_result.stderr}')

        return result, helm_update_result.returncode

    def helm_generate_update_command(self, target_release):
        """
        Generate the helm command that will run the update
        target_release: the new chart version
        """

        install_params_from_payload = json.loads(self.job.get('payload', '{}'))
        log.info(json.dumps(install_params_from_payload, indent=2))

        modules = install_params_from_payload['config-files']
        for module in modules:
            log.debug("Found module: %s",module)

        project_name = install_params_from_payload['project-name']
        if "nuvlaedge-" in project_name:
            log.debug(f"project name index : {len('nuvlaedge-')}")
            project_uuid = project_name[len("nuvlaedge-"):]
            log.debug(f"Found UUID : {project_uuid}")
        helm_repository = "nuvlaedge/nuvlaedge"
        peripherals = self.get_helm_peripherals(modules)
        env_vars = self.get_env_vars_string(install_params_from_payload)
        working_dir = self.get_working_dir(install_params_from_payload)
        mandatory_args = \
            " --set HOME=%s --set NUVLAEDGE_UUID=nuvlabox/%s --set kubernetesNode=$THE_HOST_NODE_NAME \
            --set NUVLAEDGE_JOB_ENGINE_LITE_IMAGE=nuvladev/job-lite:issue-112-update-ne \
            --set vpnClient=true"%(f'{working_dir}',f'{project_uuid}',)
        ## temporary to allow testing... FIXME
        helm_dep_test_pre_cmd = "'cd /root/deployment; "
        helm_dep_test_post_cmd = " ./helm'"
        helm_repository = ""
        helm_namespace = " -n default"
        helm_update_cmd = helm_dep_test_pre_cmd + \
                "helm upgrade %s %s %s --version %s %s %s %s"\
                    %(f'{project_name}',f'{helm_repository}', \
                      f'{helm_namespace}', \
                      f'{target_release}', \
                      f'{mandatory_args}', \
                      f'{peripherals}', \
                      f'{env_vars}',) \
                   + helm_dep_test_post_cmd

        log.info(f"Helm upgrade command: \n {helm_update_cmd}")

        return helm_update_cmd
    
    def get_working_dir(self, install_params_from_payload):
        """
        Parse the payload and return a formatted string of helm environment variables
        """
        working_dir="/root"

        if install_params_from_payload['working-dir']:
            return install_params_from_payload['working-dir']
        # do we test that the working dir exists?

        return working_dir

    def get_env_vars_string(self, install_params_from_payload):
        """
        Parse the payload and return a formatted string of helm environment variables
        """

        new_vars_string = ''
        env_pair_pattern = r"^\w+=\w+$"

        envs = install_params_from_payload['environment']
        for env_pair in envs:
            log.debug(f"Environment pair: {env_pair}")
            env_pair_mod = "".join(env_pair.split())
            re_result = re.match(env_pair_pattern,env_pair_mod)
            log.debug(f"Matching result: {re_result}")
            if re_result:
                new_vars_string = new_vars_string + " --set " + env_pair_mod
                log.debug(f"Current env var string: \n{new_vars_string}")

        log.info(f"Environment list arguments: \n {new_vars_string}")

        return new_vars_string

    def create_job_name(self, the_job_name, k=5):
        """
        Create the job name with random string attached
        """
        new_job_name = the_job_name + "-" + ''.join(random.choices(string.digits, k=k))

        return new_job_name

    def check_target_release(self, helm_log_result, target_release, current_version):
        """
        Check the status of the target release
        """
        if target_release not in helm_log_result.stdout:
            result = "Updating chart version change from %s to %s"%(f'{current_version}',f'{target_release}')
            log.info(result)
        else:
            result = "There is no chart version change from %s to %s"\
                %(f'{current_version}',f'{target_release}')
            log.info(result)
        return result

    def check_project_name(self, helm_log_result, project_name):
        """
        Check the status of the project name (namespace)
        """
        if project_name not in helm_log_result.stdout:
            result = \
            "Project namespace does not match between helm and nuvla %s"%(f'{project_name}')
            log.info(result)
            return False

        return True
    
    def get_helm_peripherals(self, modules: []):
        """
        Generate the correct helm-specific string for update command
        """
        peripherals = ""

        possible_modules = ["USB", "Bluetooth", "GPU", "Modbus", "Network", "security"]
        for module in modules:
            for module_test in possible_modules:
                if module_test.lower() in module.lower():
                    peripherals = peripherals + " --set peripheralManager" + module_test + "=true "
        log.info("Found peripherals list: %s",peripherals)
        return peripherals

    @should_connect
    def read_a_log_file(self, the_job_name):
        """
        Read the log of a kubernetes batch job

        vars:
        the_job_name: self explanatory... the name of the job
        """

        read_log_cmd = self.build_cmd_line(['logs', self.KUB_JOB() + the_job_name])
        log_result = execute_cmd(read_log_cmd)
        log.info('The log result is:\n%s',log_result.stdout)

        return log_result

    @should_connect
    def run_helm_container(self, the_job_name, the_helm_command):
        """
        Generic to run a container with a helm command
        """

        helm_manifest="""
        apiVersion: batch/v1
        kind: Job
        metadata:
          name: {job_name}
        spec:
          ttlSecondsAfterFinished: {ttl_sec}
          template:
            spec:
              containers:
              - name: {job_name}
                image: {helm_image}
                ports:
                env:
                - name: THE_HOST_NODE_NAME
                  valueFrom:
                    fieldRef:
                      fieldPath: spec.nodeName
                - name: KUBECONFIG
                  value: {kube_config}
                command: {helm_command}
                volumeMounts:
                - name: kube-config
                  mountPath: /root/.kube
                - name: helm-config
                  mountPath: /root/.config/helm
                - name: helm-cache
                  mountPath: /root/.cache/helm
                - name: deployment-path
                  mountPath: /root/deployment
              volumes:
              - name: kube-config
                hostPath:
                  path: {host_kube_config}
              - name: helm-config
                hostPath:
                  path: {host_helm_config}
              - name: helm-cache
                hostPath:
                  path: {host_helm_cache}
              - name: deployment-path
                hostPath:
                  path: {host_deployment_path}
              restartPolicy: Never
        """

        the_helm_image = "nuvladev/nuvlaedge:issue-112-update" # changed for production
        the_kube_config = "/root/.kube/config"
        the_host_kube_config = "/root/.kube"
        the_host_helm_config = "/root/.config/helm"
        the_host_helm_cache = "/root/.cache/helm"
        time_to_live = "60" # for production, once thoroughly tested this should be set to 1 or so
        the_host_deployment_path = "/root/deployment"

        base_command = "['sh', '-c',"
        cmd = the_helm_command
        end_command = "]"

        built_command = base_command + cmd + end_command

        formatted_helm_yaml_manifest = \
            helm_manifest.format(\
            job_name = the_job_name, \
            helm_image = the_helm_image, \
            kube_config = the_kube_config, \
            host_kube_config = the_host_kube_config, \
            host_helm_config = the_host_helm_config, \
            host_helm_cache = the_host_helm_cache, \
            ttl_sec = time_to_live, \
            helm_command = built_command, \
            host_deployment_path = the_host_deployment_path \
            )

        logging.debug("The re-formatted YAML is %s ", formatted_helm_yaml_manifest)

        helm_result = self.apply_a_manifest(formatted_helm_yaml_manifest)

        self.check_job_success(the_job_name) # does this make sense?

        return helm_result

    def apply_a_manifest(self, formatted_helm_yaml_manifest):
        """
        Run a manifest in a temporary directory
        """
        the_manifest = "the_manifest"

        with TemporaryDirectory() as tmp_dir_name:
            manifest_path = tmp_dir_name + '/' + the_manifest
            with open(manifest_path, 'w',encoding="utf-8") \
                as helm_manifest_file:
                helm_manifest_file.write(formatted_helm_yaml_manifest)
            helm_cmd = \
                self.build_cmd_line(['apply', '-f', manifest_path])
            helm_result = execute_cmd(helm_cmd)
            log.debug('The result of the helm container : %s',helm_result)

        return helm_result

    def check_job_success_old(self, the_job_name, success = "1/1"):
        """
        Check that a job has completed
        Runs until the success criteria is met

        job_name: the name of the Job in kubernetes
        success: the string that is present when a Job has completed

        """
        while True:
            check_cmd = \
                self.build_cmd_line(['get', self.KUB_JOB() + the_job_name])
            check_result = execute_cmd(check_cmd)
            log.debug("The check result is:\n%s",check_result.stdout)

            if success in check_result.stdout:
                return
            
    def check_job_success(self, the_job_name, success = "1/1"):
        """
        Check that a job has completed
        Runs until the success criteria is met

        job_name: the name of the Job in kubernetes
        success: the string that is present when a Job has completed

        """

        timeout = 5 # give ourselves 5 minutes for job to complete?

        t_end = time.time() + 60 * timeout

        while time.time() < t_end:
            check_cmd = \
                self.build_cmd_line(['get', self.KUB_JOB() + the_job_name])
            check_result = execute_cmd(check_cmd)
            log.debug("The check result is:\n%s",check_result.stdout)

            if success in check_result.stdout:
                return
            

class K8sSSHKey(Kubernetes):
    '''
    Class to handle SSH keys. Adding and revoking
    '''
    # def __init__(self, job):
    def __init__(self, **kwargs):

        self.job = kwargs.get("job")
        if not self.job.is_in_pull_mode:
            raise ValueError('This action is only supported by pull mode')

        self.api = kwargs.get("api")

        self.nuvlabox_resource = self.api.get(kwargs.get("nuvlabox_id"))

        path = '/srv/nuvlaedge/shared' # FIXME: needs to be parametrised.
        super(K8sSSHKey, self).__init__(ca=open(f'{path}/ca.pem',encoding="utf8").read(),
                                          key=open(f'{path}/key.pem',encoding="utf8").read(),
                                          cert=open(f'{path}/cert.pem',encoding="utf8").read(),
                                          endpoint=get_kubernetes_local_endpoint())

        # borrowed from nuvlabox.py
        self.ne_image_registry = os.getenv('NE_IMAGE_REGISTRY', '')
        self.ne_image_org = os.getenv('NE_IMAGE_ORGANIZATION', 'sixsq')
        self.ne_image_repo = os.getenv('NE_IMAGE_REPOSITORY', 'nuvlaedge')
        self.ne_image_tag = os.getenv('NE_IMAGE_TAG', 'latest')
        self.ne_image_name = os.getenv('NE_IMAGE_NAME', f'{self.ne_image_org}/{self.ne_image_repo}')
        self.base_image = f'{self.ne_image_registry}{self.ne_image_name}:{self.ne_image_tag}'

    @should_connect
    def k8s_ssh_key(self, action, pubkey, user_home):
        '''Doc string'''

        log.debug('CA file %s ', self.ca)
        log.debug('User certificate file %s ', self.cert)
        log.debug('User key file %s ', self.key)
        log.debug('Endpoint %s ', self.endpoint)
        log.debug('User home directory %s ', user_home)

        reboot_yaml_manifest = """
        apiVersion: batch/v1
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
                  value: {pubkey_string}
                volumeMounts:
                - name: ssh-key-vol
                  mountPath: {mount_path}
              volumes:
              - name: ssh-key-vol   
                hostPath:
                  path: {host_path_ssh}
              restartPolicy: Never

        """

        image_name = self.base_image
        mount_path = tempfile.gettempdir()
        sleep_value = 2
        base_command = "['sh', '-c',"
        if action.startswith('revoke'):
            cmd = "'grep -v \"${SSH_PUB}\" %s > \
                    /tmp/temp && mv /tmp/temp %s && echo Success deleting public key'" \
                      % (f'{mount_path}/.ssh/authorized_keys',
                         f'{mount_path}/.ssh/authorized_keys')
            the_job_name="revoke-ssh-key"
        else:
            cmd = "'sleep %s && echo -e \"${SSH_PUB}\" >> %s && echo Success adding public key'" \
                % (f'{sleep_value}', f'{mount_path}/.ssh/authorized_keys')
            the_job_name="add-ssh-key"
        end_command = "]"

        built_command = base_command + cmd + end_command
        log.debug("The generated command is : %s",built_command)

        formatted_reboot_yaml_manifest = \
            reboot_yaml_manifest.format(job_name = the_job_name, \
            host_path_ssh = user_home, \
            command = built_command, pubkey_string = pubkey, \
            mount_path = mount_path, image_name = image_name)

        logging.debug("The re-formatted YAML is %s ", formatted_reboot_yaml_manifest)

        with TemporaryDirectory() as tmp_dir_name:
            with open(tmp_dir_name + '/reboot_job_manifest.yaml', 'w',encoding="utf-8") \
                as reboot_manifest_file:
                reboot_manifest_file.write(formatted_reboot_yaml_manifest)
            cmd_ssh_key = \
                self.build_cmd_line(['apply', '-f', tmp_dir_name + '/reboot_job_manifest.yaml'])
            ssh_key_result = execute_cmd(cmd_ssh_key)
            log.debug('The result of the ssh key addition : %s',ssh_key_result)
        return ssh_key_result

    def handle_ssh_key(self, action, pubkey, credential_id, nuvlabox_id):
        """
        General function to either add or revoke an SSH key from a nuvlabox 

        Arguments:
        action: value can be add or revoke
        pubkey: the public key string to be added or revoked
        credential_id: the nuvla ID of the credential
        nuvlabox_id: the id UID of the nuvlabox
        """
        nuvlabox_status = self.api.get("nuvlabox-status").data
        nuvlabox_resource = self.api.get(nuvlabox_id)
        nuvlabox = nuvlabox_resource.data
        logging.debug('nuvlabox: %s',nuvlabox)
        user_home = self._get_user_home(nuvlabox_status)
        ssh_keys = nuvlabox.get('ssh-keys', [])
        logging.debug("Current ssh keys:\n%s\n", ssh_keys)
        logging.info("The credential being added/revoked is: %s",credential_id)
        if action.startswith('add'):
            if credential_id in ssh_keys:
                logging.debug('The credential ID to be added is already present: %s',credential_id)
                self.job.update_job(status_message=json.dumps("SSH public key already present"))
                return 1
        else:
            if credential_id not in ssh_keys:
                logging.debug('The credential ID to be revoked is not in the list: %s',\
                    credential_id)
                self.job.update_job(status_message=json.dumps\
                    ("The credential ID to be revoked is not in the list"))
                return 1
        result = self.k8s_ssh_key(action, pubkey, user_home)
        if result.returncode == 0 and not result.stderr:
            self.update_results(credential_id, ssh_keys, action, nuvlabox_resource)
            return 0
        self.job.update_job(status_message=json.dumps("The SSH public key add/revoke has failed."))
        return 2

    def update_results(self, credential_id, ssh_keys, action, nuvlabox_resource):
        """Update the server side nuvla.io list of credentials

        Arguments:
        credential_id: the nuvla ID of the credential
        ssh_keys: the list of ssh keys for the nuvlabox
        action: either add or revoke the ssh key
        nuvlabox_resource: the nuvlabox resource ID
        """
        logging.debug('Adding or deleting credential ID: %s',credential_id)
        if action.startswith('add'):
            update_payload = ssh_keys + [credential_id]
            message_out="SSH public key added successfully"
        else:
            try:
                ssh_keys.remove(credential_id)
                logging.debug('The SSH keys (update_payload) after removal :\n%s\n',ssh_keys)
                update_payload = ssh_keys
            except ValueError:
                update_payload = None
            message_out="SSH public key deleted successfully"

        if update_payload is not None:
            # self.commission(update_payload)
            logging.debug('The update payload is:\n%s\n',update_payload)
            self.api.operation(nuvlabox_resource, "commission", {"ssh-keys": update_payload})
            self.job.update_job(status_message=json.dumps(message_out))
            return 0
        return 1

    def _get_user_home(self, nuvlabox_status):
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
                logging.info('Attention: The user home has been set to: %s ',user_home)
        return user_home
