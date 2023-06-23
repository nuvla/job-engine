# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
from nuvla.api.util.filter import filter_or

from ..actions import action

action_name = 'create_deployment_set'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentSetCreateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = self.job.api
        self.user_api = job.get_user_api()
        self.dep_set_id = self.job['target-resource']['href']
        self.deployment_set = self.user_api.get(self.dep_set_id)
        self.plan = self.user_api.operation(self.deployment_set, 'plan').data
        self.progress_increment = 90 / len(self.plan) if self.plan else 90
        self.start = self.deployment_set.data['start']

    def _create_deployment(self, target, application):
        return self.user_api.add('deployment',
                                 {'module': {'href': application},
                                  'parent': target,
                                  'deployment-set': self.dep_set_id}).data['resource-id']

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

    def _create(self):
        log.info('Create {}.'.format(self.dep_set_id))
        progress = 10
        self.job.set_progress(progress)
        self.user_api.edit(self.dep_set_id, {'state': 'CREATING'})
        for el in self.plan:
            target = el['credential']
            application = el["application"]
            application_href = f'{application["id"]}_{application["version"]}'
            deployment_id = self._create_deployment(target, application_href)
            deployment = self.user_api.get(deployment_id).data
            self._update_env_deployment(deployment, application)
            self._update_regs_creds_deployment(deployment, application)
            self.user_api.edit(deployment_id, deployment)
            progress += self.progress_increment
        self.user_api.edit(self.dep_set_id, {'state': 'CREATED'})
        if self.start:
            self.user_api.operation(self.user_api.get(self.dep_set_id), "start")
        return 0

    def do_work(self):
        return self._create()
