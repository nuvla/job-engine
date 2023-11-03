# -*- coding: utf-8 -*-

import logging
from ..utils.bulk_action import BulkAction


class BulkDeploymentSetApply(BulkAction):

    def __init__(self, _, job):
        super().__init__(_, job)
        self.dep_set_id = self.job['target-resource']['href']
        self.action_name = None

    def get_todo(self):
        deployment_set = self.user_api.get(self.dep_set_id)
        return deployment_set.data['operational-status']

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
        filter_subtype_infra = f'subtype={str(["swarm", "kubernetes"])}'
        filter_infra = f'parent="{nuvlabox["infrastructure-service-group"]}" ' \
                       f'and {filter_subtype_infra}'
        infras = self.user_api.search('infrastructure-service',
                                      filter=filter_infra, select='id').resources
        if len(infras) > 0:
            return infras[0].id

    def _get_cred(self, target):
        infra_id = self._get_infra(target)
        if infra_id:
            filter_cred_subtype = f'subtype={str(["infrastructure-service-swarm", "infrastructure-service-kubernetes"])}'
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
            deployment_id = deployment_to_update[0]['id']
            deployment = self.user_api.get(deployment_id)
            deployment_data = deployment.data
            application = deployment_to_update[1]["application"]
            application_href = f'{application["id"]}_{application["version"]}'
            self._update_env_deployment(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.user_api.edit(deployment_id, deployment_data)
            self.user_api.operation(deployment, 'fetch-module',
                                    {'module-href': application_href})
            action = 'update' if deployment.operations.get('update') else 'start'
            self.user_api.operation(deployment, action,
                                    {'low-priority': True,
                                     'parent-job': self.job.id})
            logging.info(f'Deployment updated: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to update deployment {deployment_to_update}: {repr(ex)}')

    def _force_remove_deployment(self, deployment_id):
        try:
            deployment = self.user_api.get(deployment_id)
            self.user_api.operation(deployment, 'force-delete')
            logging.info(f'Deployment removed: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to remove {deployment_id}: {repr(ex)}')

    def _remove_deployment(self, deployment_id):
        try:
            self.user_api.delete(deployment_id)
            logging.info(f'Deployment removed: {deployment_id}')
        except Exception as ex:
            logging.error(f'Failed to remove {deployment_id}: {repr(ex)}')

    def _apply_op_status(self, func, operational_status, k):
        elements = operational_status.get(k, [])
        copy_elements = elements[:]
        for el in copy_elements:
            func(el)
            elements.remove(el)
            self._push_result()

    def bulk_operation(self):
        op_status = self.result['TODO']
        if op_status['status'] == 'NOK':
            self._apply_op_status(self._add_deployment, op_status, 'deployments-to-add')
            # FIXME : find a cleaner better way to avoid orphan containers
            self._apply_op_status(self._force_remove_deployment, op_status, 'deployments-to-remove')
            self._apply_op_status(self._update_deployment, op_status, 'deployments-to-update')

    def do_work(self):
        logging.info(f'Start bulk deployment set apply {self.action_name} {self.job.id}')
        self.run()
        logging.info(f'End of bulk deployment set apply {self.action_name} {self.job.id}')
