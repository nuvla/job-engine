# -*- coding: utf-8 -*-

import json
import logging
from nuvla.api import Api
from nuvla.api.util.filter import filter_or

from ..actions import action

action_name = 'create_deployment_set'

log = logging.getLogger(action_name)


def app_compatible_with_target(target_subtype, app_subtype):
    return (app_subtype == 'application_kubernetes' and target_subtype == 'infrastructure-service-kubernetes') or (
                app_subtype != 'application_kubernetes' and target_subtype != 'infrastructure-service-kubernetes')


def app_id(application):
    return application.split("_")[0]


@action(action_name, True)
class DeploymentSetCreateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = self.job.api
        self.user_api = self._get_user_api()
        self.dep_set_id = self.job['target-resource']['href']
        self.deployment_set = self.user_api.get(self.dep_set_id).data
        self.targets = self.deployment_set['spec']['targets']
        self.applications = self.deployment_set['spec']['applications']
        self.existing_deployments = self._load_existing_deployments()
        self.targets_info = self._load_targets_info()
        self.applications_info = self._load_applications_info()

    def _get_user_api(self):
        authn_info = json.loads(self.job['payload'])['authn-info']
        insecure = not self.api.session.verify
        return Api(endpoint=self.api.endpoint, insecure=insecure,
                   persist_cookie=False, reauthenticate=True,
                   authn_header=f'{authn_info["user-id"]} '
                                f'{authn_info["active-claim"]} '
                                f'{" ".join(authn_info["claims"])}')

    def _load_existing_deployments(self):
        query_result = self.user_api.search(
            'deployment',
            filter=f'deployment-set="{self.dep_set_id}"',
            last=10000,
            select='id, parent, module').resources
        return set(
            [(r.data['parent'], r.data['module']['href'])
             for r in query_result])

    def _load_targets_info(self):
        return \
            {cred.id: cred for cred in
             self.user_api.search(
                 'credential',
                 filter=filter_or(
                     [f'id="{target}"' for target in self.targets]),
                 last=10000,
                 select='id, subtype').resources} if len(
                self.targets) > 0 else {}

    def _load_applications_info(self):
        return {module.id: module for module in self.user_api.search(
            'module',
            filter=filter_or(
                [f'id="{app_id(app)}"' for app in self.applications]),
            last=10000,
            select='id, subtype').resources} if len(
            self.applications) > 0 else {}

    def _compatible_with_target(self, target_subtype, application):
        app_subtype = self.applications_info[app_id(application)].data['subtype']
        return app_compatible_with_target(target_subtype, app_subtype)

    def _create_deployment(self, target, application):
        self.user_api.add('deployment',
                          {'module': {'href': application},
                           'parent': target,
                           'deployment-set': self.dep_set_id})

    def _create(self):
        dep_set_id = self.job['target-resource']['href']
        log.info('Create {}.'.format(dep_set_id))
        progress = 10
        self.job.set_progress(progress)
        progress_increment = 90 / len(self.targets)
        for target in self.targets:
            target_subtype = self.targets_info[target].data['subtype']
            for application in self.applications:
                if (target, application) not in self.existing_deployments \
                        and self._compatible_with_target(target_subtype, application):
                    self._create_deployment(target, application)
            progress += progress_increment
            self.job.set_progress(int(progress))
        self.user_api.edit(dep_set_id, {'state': 'CREATED'})
        return 0

    def do_work(self):
        return self._create()