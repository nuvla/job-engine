# -*- coding: utf-8 -*-
import logging

from datetime import datetime
from typing import List, Tuple, Any

from nuvla.api.resources import Deployment

from .connector import ConnectorCOE
from .helm_driver import Helm
from .k8s_driver import Kubernetes
from .utils import join_stderr_stdout, interpolate_and_store_files, \
    string_interpolate_env_vars, run_in_tmp_dir


# TODO: this logger is used for k8s and helm. Refactor is needed.
log = logging.getLogger('k8s_connector')


def instantiate_from_cimi(api_infra_service, api_credential, **kwargs):
    _kwargs = dict(ca=api_credential.get('ca', '').replace("\\n", "\n"),
                   cert=api_credential.get('cert', '').replace("\\n", "\n"),
                   key=api_credential.get('key', '').replace("\\n", "\n"),
                   endpoint=api_infra_service.get('endpoint'))
    if api_infra_service.get('subtype') == 'kubernetes':
        return AppMgmtK8s(**_kwargs)
    elif api_infra_service.get('subtype') == 'helm':
        job = kwargs.get('job')
        if not job:
            raise ValueError('Job object is required for AppMgmtHelm '
                             'instantiation.')
        return AppMgmtHelm(job.nuvlaedge_shared_path, **_kwargs)


class AppMgmtK8s(ConnectorCOE):
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

    def start(self, **kwargs) -> Tuple[str, List[dict], Any]:
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

        return result, objects, {}

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


class AppMgmtHelm(ConnectorCOE):
    """Class providing Helm-based application management functionalities.
    """

    def __init__(self, ne_db: str, **kwargs):
        """
        :param ne_db: path to NuvlaEdge local filesystem database.
        :param kwargs:
        """
        super().__init__(**kwargs)

        self.helm = Helm(ne_db, **kwargs)

    @staticmethod
    def helm_release_name(string: str):
        return 'release-' + string

    def get_helm_release(self, helm_release, namespace) -> dict:
        release = {}
        releases = self.helm.list(namespace, release=release)
        if releases:
            return releases[0]
        log.warning(f'Helm release "{helm_release}" not found in '
                    f'namespace {namespace}.')
        return release

    @run_in_tmp_dir
    def _op_install_upgrade(self, op: str, **kwargs) \
            -> Tuple[str, List[dict], dict]:
        deployment = kwargs['deployment']
        namespace = kwargs['name']
        helm_release = self.helm_release_name(namespace)

        helm_repo_cred = kwargs.get('helm_repo_cred')
        helm_repo_url = kwargs.get('helm_repo_url')
        work_dir = kwargs.get('work_dir', '.')

        app_content = Deployment.module_content(deployment)
        chart_name = app_content.get('helm-chart-name')
        version = app_content.get('helm-chart-version')
        helm_absolute_url = app_content.get('helm-absolute-url')
        chart_values_yaml = app_content.get('helm-chart-values')

        env = kwargs.get('env')

        interpolate_and_store_files(env, kwargs.get('files'), dir_path=work_dir)

        if chart_values_yaml and env:
            chart_values_yaml = string_interpolate_env_vars(chart_values_yaml, env)

        registries_auth = kwargs.get('registries_auth')
        # FIXME: check how to handle the secrets during upgrade.
        if registries_auth and op != 'upgrade':
            self.helm.k8s.create_namespace(namespace, exists_ok=True)
            self.helm.k8s.add_secret_image_registries_auths(registries_auth,
                                                            namespace)
        try:
            result = self.helm.op_install_upgrade(op, helm_release,
                                                  helm_repo_url, helm_repo_cred,
                                                  helm_absolute_url, chart_name,
                                                  version, namespace,
                                                  chart_values_yaml)
        except Exception as ex:
            log.exception(f'Failed to {op} Helm chart: {ex}')
            if 'cannot re-use a name' in ex.args[0]:
                args = list(ex.args)
                args[0] = (args[0].strip() +
                           f'. Helm release: {helm_release}. '
                           f'Currently running: {self.helm.list(namespace)}')
                ex.args = tuple(args)
                raise ex
            raise ex

        objects = self.get_services(namespace, None)

        release = self.get_helm_release(helm_release, namespace)

        return result.stdout, objects, release

    def start(self, **kwargs) -> Tuple[str, List[dict], dict]:
        return self._op_install_upgrade('install', **kwargs)

    def update(self, **kwargs) -> Tuple[str, List[dict], dict]:
        try:
            return self._op_install_upgrade('upgrade', **kwargs)
        except Exception as ex:
            if 'UPGRADE FAILED' in ex.args[0]:
                if 'has no deployed releases' in ex.args[0]:
                    log.warning('No release found. Run installation instead.')
                    return self._op_install_upgrade('install', **kwargs)
            raise ex

    def stop(self, **kwargs) -> str:
        namespace = kwargs['name']
        helm_release = self.helm_release_name(namespace)
        try:
            result = self.helm.uninstall(helm_release, namespace)
        except Exception as ex:
            log.exception(f'Failed to uninstall Helm chart: {ex}')
            if 'not found' in ex.args[0]:
                log.warning(f'Helm release "{helm_release}" not found.')
                return ex.args[0]
            raise ex
        return result.stdout

    def list(self):
        """
        This method is here to simply follow the interface. It is not used.
        """
        pass

    def get_services(self, deployment_uuid: str, _, **kwargs) -> list:
        """
        Returns both K8s Services and Deployments by `deployment_uuid`.

        :param deployment_uuid: Deployment UUID
        :param _: this parameter is ignored.
        :param kwargs: this parameter is ignored.
        :return: list of dicts
        """
        objects = ['deployments',
                   'services']
        return self.helm.k8s.get_objects(deployment_uuid, objects)
