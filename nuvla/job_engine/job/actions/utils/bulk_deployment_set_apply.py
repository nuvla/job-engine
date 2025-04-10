# -*- coding: utf-8 -*-
from pyexpat.errors import messages

from .bulk_action import ActionCallException, ActionException, BulkAction, SkippedActionException


def get_dg_owner_api(job):
    authn_info = job.payload['dg-owner-authn-info']
    return job.get_api(authn_info)

def get_dg_api(job):
    authn_info = job.payload['dg-authn-info']
    return job.get_api(authn_info)

class EdgeResolver:
    def __init__(self, dg_owner_api, dg_subtype):
        self.edges = {}
        self.dg_owner_api = dg_owner_api
        self.dg_subtype = dg_subtype

    @staticmethod
    def _is_edge_target(target):
        return target and target.startswith('nuvlabox/')

    def _get_edge(self, target):
        edge = self.edges.get(target)
        if not edge:
            try:
                edge = self.dg_owner_api.get(target).data
            except Exception as ex:
                raise SkippedActionException('Edge not found', resource_id=target, message=str(ex))
            self.edges[target] = edge
        return edge

    def _edge_credential(self, edge):
        cred = edge.get('credential')
        if cred == '':
            return None
        else:
            infra_id = self._get_infra(edge)
            creds = []
            if infra_id:
                filter_cred_subtype = f'subtype={["infrastructure-service-swarm", "infrastructure-service-kubernetes"]}'
                filter_cred = f'parent="{infra_id}" and {filter_cred_subtype}'
                creds = self.dg_owner_api.search('credential', filter=filter_cred, select='id').resources
            cred = creds[0].id if len(creds) > 0 else ''
            self.edges[edge.get('id')]['credential'] = cred
        return cred

    def _get_infra(self, edge):
        if self.dg_subtype in ["docker-swarm", "docker-compose"]:
            infra_subtypes = ["swarm"]
        elif self.dg_subtype == "kubernetes":
            infra_subtypes = ["kubernetes"]
        else:
            # TODO: once subtype of deployment-set has been back-filled for existing DGs throw an error instead
            infra_subtypes = ["swarm", "kubernetes"]
        filter_subtype_infra = f'subtype={infra_subtypes}'
        filter_infra = f'parent="{edge["infrastructure-service-group"]}" ' \
                       f'and {filter_subtype_infra}'
        infras = self.dg_owner_api.search('infrastructure-service',
                                          filter=filter_infra,
                                          orderby='subtype:desc',
                                          select='id').resources
        if len(infras) > 0:
            return infras[0].id

    def _get_cred(self, target):
        infra_id = self._get_infra(target)
        if infra_id:
            filter_cred_subtype = f'subtype={["infrastructure-service-swarm", "infrastructure-service-kubernetes"]}'
            filter_cred = f'parent="{infra_id}" and {filter_cred_subtype}'
            creds = self.dg_owner_api.search('credential', filter=filter_cred, select='id').resources
            if len(creds) > 0:
                return creds[0].id

    def throw_edge_offline(self, target):
        if EdgeResolver._is_edge_target(target):
            edge = self._get_edge(target)
            if not edge.get('online', False):
                raise SkippedActionException(
                    'Offline Edge', resource_id=target, resource_name=edge.get('name'))

    def resolve_credential(self, target):
        if EdgeResolver._is_edge_target(target):
            edge = self._get_edge(target)
            cred = self._edge_credential(edge)
            if cred is None:
                raise SkippedActionException(
                    'Edge credential not found', resource_id=target, resource_name=edge.get('name'))
            return cred
        else:
            return target

class BulkDeploymentSetApply(BulkAction):
    KEY_DEPLOYMENTS_TO_ADD = 'deployments-to-add'
    KEY_DEPLOYMENTS_TO_UPDATE = 'deployments-to-update'
    KEY_DEPLOYMENTS_TO_REMOVE = 'deployments-to-remove'

    def __init__(self, job, action_name):
        super().__init__(job, action_name)
        self.dg_owner_api = get_dg_owner_api(job)
        self.dg_api = get_dg_api(job)
        self.dep_set_id = self.job['target-resource']['href']
        self.dep_set = self.dg_api.get(self.dep_set_id)
        self.action_name = None
        self._log = None
        self.operations = {self.KEY_DEPLOYMENTS_TO_ADD: self._add_deployment,
                           self.KEY_DEPLOYMENTS_TO_UPDATE: self._update_deployment,
                           self.KEY_DEPLOYMENTS_TO_REMOVE: self._remove_deployment}
        self.api_endpoint = None
        self.edge_resolver = EdgeResolver(self.dg_owner_api,
                                          self.dep_set.data.get('subtype'))

    @staticmethod
    def _action_name_todo_el(operational_status, key):
        return [(key, el) for el in operational_status.get(key, [])]

    def get_todo(self):
        operational_status = self.dg_api.operation(self.dep_set, 'operational-status').data
        self.log.info(f'{self.dep_set_id} - Operational status: {operational_status}')
        self.api_endpoint = self.dep_set.data.get('api-endpoint')
        todo = (self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_ADD) +
                self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_UPDATE) +
                self._action_name_todo_el(operational_status, self.KEY_DEPLOYMENTS_TO_REMOVE))
        return todo

    def _create_deployment(self, credential, application, app_set):
        return self.dg_owner_api.add('deployment',
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

    def _update_api_endpoint(self, deployment):
        if self.api_endpoint:
            deployment['api-endpoint'] = self.api_endpoint

    def _load_reset_deployment(self, deployment_id, application):
        application_href = f'{application["id"]}_{application["version"]}'
        module = self.dg_owner_api.get(application_href)
        deployment = self.dg_api.get(deployment_id)
        deployment_data = deployment.data
        deployment_data['module']['href'] = application_href
        deployment_data['module']['content']['environmental-variables'] = module.data['content'].get(
            'environmental-variables', [])
        return deployment_data

    def _add_deployment(self, deployment_to_add):
        try:
            target = deployment_to_add['target']
            self.edge_resolver.throw_edge_offline(target)
            credential = self.edge_resolver.resolve_credential(target)
            application = deployment_to_add['application']
            application_href = f'{application["id"]}_{application["version"]}'
            app_set = deployment_to_add['app-set']
            deployment_id = self._create_deployment(credential, application_href, app_set)
            self.log.info(f'{self.dep_set_id} - Add deployment: {deployment_id}')
            deployment = self.dg_owner_api.get(deployment_id)
            deployment_data = deployment.data
            self._update_api_endpoint(deployment_data)
            self._update_env_deployment(deployment_data, application)
            self._update_files(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.dg_owner_api.edit(deployment_id, deployment_data)
            self.log.debug(f'{self.dep_set_id} - starting deployment: {deployment_id}')
            return self.dg_api.operation(deployment, 'start',
                                         {'low-priority': True,
                                          'parent-job': self.job.id})
        except ActionException as ex:
            raise ex
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to add deployment {deployment_to_add}: {repr(ex)}')
            raise ActionCallException('Deployment add failed', message=str(ex), context=deployment_to_add)

    def _update_deployment(self, deployment_to_update):
        deployment_id = None
        try:
            deployment_id = deployment_to_update[0]['id']
            target = deployment_to_update[1]['target']
            self.edge_resolver.throw_edge_offline(target)
            self.log.info(f'{self.dep_set_id} - Update deployment: {deployment_id}')
            application = deployment_to_update[1]['application']
            deployment_data = self._load_reset_deployment(deployment_id, application)
            self._update_api_endpoint(deployment_data)
            self._update_env_deployment(deployment_data, application)
            self._update_files(deployment_data, application)
            self._update_regs_creds_deployment(deployment_data, application)
            deployment = self.dg_owner_api.edit(deployment_id, deployment_data)
            action = 'update' if deployment.operations.get('update') else 'start'
            self.log.debug(f'{self.dep_set_id} - {action}ing deployment: {deployment_id}')
            return self.dg_api.operation(deployment, action,
                                         {'low-priority': True,
                                          'parent-job': self.job.id})
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to update deployment {deployment_to_update}: {repr(ex)}')
            raise ActionCallException('Deployment update failed', resource_id=deployment_id, message=str(ex), context=deployment_to_update)

    def _remove_deployment(self, deployment_id):
        try:
            self.log.info(f'{self.dep_set_id} - Remove deployment: {deployment_id}')
            deployment = self.dg_api.get(deployment_id)
            if deployment.data['state'] == 'STOPPED':
                self.log.debug(f'{self.dep_set_id} - deleted deployment: {deployment_id}')
                return self.dg_api.delete(deployment_id)
            else:
                target = deployment.data.get('nuvlabox')
                self.edge_resolver.throw_edge_offline(target)
                self.log.debug(f'{self.dep_set_id} - stopping/delete deployment: {deployment_id}')
                return self.dg_api.operation(deployment, 'stop',
                                             data={'low-priority': True,
                                                   'parent-job': self.job.id,
                                                   'delete': True})
        except Exception as ex:
            self.log.error(f'{self.dep_set_id} - Failed to remove {deployment_id}: {repr(ex)}')
            raise ActionCallException('Deployment remove failed', resource_id=deployment_id, message=str(ex))

    def _get_operation(self, operation_name: str):
        func = self.operations.get(operation_name)
        if not func:
            raise ActionCallException('Unknown deployment set operation', context={'operation_name': operation_name})
        return func

    def todo_resource_id(self, todo_el):
        action_name, data = todo_el
        if action_name == self.KEY_DEPLOYMENTS_TO_ADD:
            return None
        elif action_name == self.KEY_DEPLOYMENTS_TO_REMOVE:
            return data
        elif action_name == self.KEY_DEPLOYMENTS_TO_UPDATE:
            return data[0]['id']

    def action(self, todo_el):
        action_name, data = todo_el
        func = self._get_operation(action_name)
        return func(data)
