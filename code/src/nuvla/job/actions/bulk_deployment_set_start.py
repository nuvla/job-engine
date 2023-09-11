# -*- coding: utf-8 -*-

import logging
from ..actions import action
from ..job import JOB_SUCCESS


@action('bulk_deployment_set_start')
class BulkDeploymentSetStartJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.user_api = job.get_user_api()
        self.dep_set_id = None

    def _create_deployment(self, credential, application, app_set):
        return self.user_api.add('deployment',
                                 {'module': {'href': application},
                                  'parent': credential,
                                  'deployment-set': self.dep_set_id,
                                  'app-set': app_set}).data['resource-id']

    @staticmethod
    def _update_env_deployment(deployment, application):
        dep_envs = deployment['module']['content'] \
            .get('environmental-variables', [])
        app_envs = application.get('environmental-variables', [])
        app_env_overwrites = {d['name']: d['value'] for d in app_envs}
        for dep_env in dep_envs:
            if dep_env['name'] in app_env_overwrites:
                dep_env['value'] = app_env_overwrites[dep_env['name']]

    @staticmethod
    def _update_regs_creds_deployment(deployment, application):
        app_regs_creds = application.get('registries-credentials')
        if app_regs_creds:
            deployment['registries-credentials'] = app_regs_creds

    def _get_infra(self, target):
        nuvlabox = self.user_api.get(target).data
        filter_subtype_infra = '(subtype="swarm" or subtype="kubernetes")'
        filter_infra = f'parent="{nuvlabox["infrastructure-service-group"]}" ' \
                       f'and {filter_subtype_infra}'
        infras = self.user_api.search('infrastructure-service',
                                      filter=filter_infra, select='id').resources
        if len(infras) > 0:
            return infras[0].id

    def _get_cred(self, target):
        infra_id = self._get_infra(target)
        if infra_id:
            filter_cred_subtype = '(subtype="infrastructure-service-swarm" or ' \
                                  'subtype="infrastructure-service-kubernetes")'
            filter_cred = f'parent="{infra_id}" and {filter_cred_subtype}'
            creds = self.user_api.search('credential', filter=filter_cred, select='id').resources
            if len(creds) > 0:
                return creds[0].id

    def _resolve_target(self, target):
        if target:
            if target.startswith('credential/'):
                return target
            elif target.startswith('nuvlabox/'):
                return self._get_cred(target)

    @staticmethod
    def _fix_transition_state(deployment_data):
        if deployment_data['state'].endswith('ING'):
            deployment_data['state'] = 'ERROR'

    def _add_deployment(self, deployment_to_add):
        try:
            target = deployment_to_add['target']
            credential = self._resolve_target(target)
            application = deployment_to_add["application"]
            application_href = f'{application["id"]}_{application["version"]}'
            app_set = deployment_to_add['app-set']
            deployment_id = self._create_deployment(credential, application_href, app_set)
            deployment = self.user_api.get(deployment_id)
            deployment_data = deployment.data
            self._update_env_deployment(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.user_api.edit(deployment_id, deployment_data)
            self.user_api.operation(deployment, 'start',
                                    {'low-priority': True,
                                     'parent-job': self.job.id})
            logging.info(f'Deployment added: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to add deployment {deployment_to_add}: {repr(ex)}')

    def _update_deployment(self, deployment_to_update):
        try:
            deployment_id =  deployment_to_update[0]['id']
            deployment = self.user_api.get(deployment_id)
            deployment_data = deployment.data
            self._fix_transition_state(deployment_data)
            application = deployment_to_update[1]["application"]
            application_href = f'{application["id"]}_{application["version"]}'
            self._update_env_deployment(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            self.user_api.edit(deployment_id, deployment_data)
            self.user_api.operation(deployment, 'fetch-module',
                                    {'module-href': application_href})
            self.user_api.operation(deployment, 'update',
                                    {'low-priority': True,
                                     'parent-job': self.job.id})
            logging.info(f'Deployment updated: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to update deployment {deployment_to_update}: {repr(ex)}')

    def _remove_deployment(self, deployment_to_remove):
        try:
            self.user_api.delete(deployment_to_remove)
            #deployment = self.user_api.get(deployment_to_remove)
            # deployment_data = deployment.data
            # self._fix_transition_state(deployment_data)
            # self.user_api.edit(deployment_to_remove, deployment_data)
            # self.user_api.operation(deployment, 'stop')
            logging.info(f'Deployment removed: {deployment_to_remove}')
        except Exception as ex:
            logging.error(f'Failed to remove {deployment_to_remove}: {repr(ex)}')

    @staticmethod
    def _apply(operational_status, k, f):
        list(map(f, operational_status.get(k, [])))

    def _on_operational_status(self, ok_fn, nok_fn):
        deployment_set = self.user_api.get(self.dep_set_id)
        op_status = self.user_api.operation(deployment_set, 'operational-status').data
        if op_status['status'] == 'OK':
            ok_fn(deployment_set, op_status)
        else:
            nok_fn(deployment_set, op_status)

    def on_op_ok(self, deployment_set, _op_status):
        self.user_api.operation(deployment_set, 'ok')
        self.job.set_state(JOB_SUCCESS)
        logging.info(f'End of bulk deployment set start with ok {self.job.id}')
        return 0

    def on_op_nok(self, deployment_set, _op_status):
        self.user_api.operation(deployment_set, 'nok')
        logging.info(f'End of bulk deployment set start with nok {self.job.id}')
        return 0

    def on_op_nok_apply(self, _deployment_set, op_status):
        self._apply(op_status, 'deployments-to-add', self._add_deployment)
        self._apply(op_status, 'deployments-to-remove', self._remove_deployment)
        self._apply(op_status, 'deployments-to-update', self._update_deployment)
        self._on_operational_status(self.on_op_ok, self.on_op_nok)

    def do_work(self):
        logging.info(f'Start bulk deployment set start {self.job.id}')
        self.dep_set_id = self.job['target-resource']['href']
        self._on_operational_status(self.on_op_ok, self.on_op_nok_apply)
