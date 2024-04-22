# -*- coding: utf-8 -*-

import logging
from ..utils.bulk_action import BulkAction


class BulkDeploymentSetApply(BulkAction):
    KEY_DEPLOYMENTS_TO_ADD = 'deployments-to-add'
    KEY_DEPLOYMENTS_TO_UPDATE = 'deployments-to-update'
    KEY_DEPLOYMENTS_TO_REMOVE = 'deployments-to-remove'

    def __init__(self, _, job):
        super().__init__(_, job)
        self.dep_set_id = self.job['target-resource']['href']
        self.action_name = None
        self._log = None
        self.operations = {self.KEY_DEPLOYMENTS_TO_ADD: self._add_deployment,
                           self.KEY_DEPLOYMENTS_TO_UPDATE: self._update_deployment,
                           self.KEY_DEPLOYMENTS_TO_REMOVE: self._remove_deployment}

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(self.action_name)
        return self._log

    @staticmethod
    def _action_name_todo_el(operational_status, key):
        return [(key, el) for el in operational_status.get(key, [])]

    def get_todo(self):
        deployment_set = self.user_api.get(self.dep_set_id)
        operational_status = self.user_api.operation(deployment_set, 'operational-status').data
        self.log.info(f'{self.dep_set_id} - Operational status: {operational_status}')
        todo = (self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_ADD) +
                self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_UPDATE) +
                self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_REMOVE))
        return todo

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
    def _update_files(deployment, application):
        dep_files = deployment['module']['content'] \
            .get('files', [])
        app_files = application.get('files', [])
        app_files_overwrites = {d['file-name']: d['file-content'] for d in app_files}
        for dep_file in dep_files:
            if dep_file['file-name'] in app_files_overwrites:
                dep_file['file-content'] = app_files_overwrites[dep_file['file-name']]

    @staticmethod
    def _update_regs_creds_deployment(deployment, application):
        app_regs_creds = application.get('registries-credentials')
        if app_regs_creds:
            deployment['registries-credentials'] = app_regs_creds

    def _get_infra(self, target):
        nuvlabox = self.user_api.get(target).data
        filter_subtype_infra = f'subtype={["swarm", "kubernetes"]}'
        filter_infra = f'parent="{nuvlabox["infrastructure-service-group"]}" ' \
                       f'and {filter_subtype_infra}'
        infras = self.user_api.search('infrastructure-service',
                                      filter=filter_infra, select='id').resources
        if len(infras) > 0:
            return infras[0].id

    def _get_cred(self, target):
        infra_id = self._get_infra(target)
        if infra_id:
            filter_cred_subtype = f'subtype={["infrastructure-service-swarm", "infrastructure-service-kubernetes"]}'
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

    def _load_reset_deployment(self, deployment_id, application):
        application_href = f'{application["id"]}_{application["version"]}'
        module = self.user_api.get(application_href)
        deployment = self.user_api.get(deployment_id)
        deployment_data = deployment.data
        deployment_data['module']['href'] = application_href
        deployment_data['module']['content']['environmental-variables'] = module.data['content'].get(
            'environmental-variables', [])
        return deployment_data

    def _add_deployment(self, deployment_to_add):
        try:
            target = deployment_to_add['target']
            credential = self._resolve_target(target)
            application = deployment_to_add["application"]
            application_href = f'{application["id"]}_{application["version"]}'
            app_set = deployment_to_add['app-set']
            deployment_id = self._create_deployment(credential, application_href, app_set)
            self.log.info(f'{self.dep_set_id} - Add deployment: {deployment_id}')
            deployment = self.user_api.get(deployment_id)
            deployment_data = deployment.data
            self._update_env_deployment(deployment_data, application)
            self._update_files(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.user_api.edit(deployment_id, deployment_data)
            self.log.debug(f'{self.dep_set_id} - starting deployment: {deployment_id}')
            self.user_api.operation(deployment, 'start',
                                    {'low-priority': True,
                                     'parent-job': self.job.id})
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to add deployment {deployment_to_add}: {repr(ex)}')

    def _update_deployment(self, deployment_to_update):
        try:
            deployment_id = deployment_to_update[0]['id']
            self.log.info(f'{self.dep_set_id} - Update deployment: {deployment_id}')
            application = deployment_to_update[1]["application"]
            deployment_data = self._load_reset_deployment(deployment_id, application)
            self._update_env_deployment(deployment_data, application)
            self._update_files(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.user_api.edit(deployment_id, deployment_data)
            action = 'update' if deployment.operations.get('update') else 'start'
            self.log.debug(f'{self.dep_set_id} - {action}ing deployment: {deployment_id}')
            self.user_api.operation(deployment, action,
                                    {'low-priority': True,
                                     'parent-job': self.job.id})
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to update deployment {deployment_to_update}: {repr(ex)}')

    def _remove_deployment(self, deployment_id):
        try:
            self.log.info(f'{self.dep_set_id} - Remove deployment: {deployment_id}')
            deployment = self.user_api.get(deployment_id)
            if deployment.data['state'] == 'STOPPED':
                self.user_api.delete(deployment_id)
                self.log.debug(f'{self.dep_set_id} - deleted deployment: {deployment_id}')
            else:
                self.log.debug(f'{self.dep_set_id} - stopping/delete deployment: {deployment_id}')
                self.user_api.operation(deployment, 'stop',
                                        data={'low-priority': True,
                                              'parent-job': self.job.id,
                                              'delete': True})
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to remove {deployment_id}: {repr(ex)}')

    def _get_operation(self, operation_name: str):
        func = self.operations.get(operation_name)
        if not func:
            raise KeyError(f'Unknown deployment set operation name: {operation_name}')
        return func

    def action(self, todo_el):
        action_name, data = todo_el
        func = self._get_operation(action_name)
        return func(data)

    def do_work(self):
        self.log.info(f'Start bulk deployment set apply {self.action_name} {self.job.id}')
        self.run()
        self.log.info(f'End of bulk deployment set apply {self.action_name} {self.job.id}')
