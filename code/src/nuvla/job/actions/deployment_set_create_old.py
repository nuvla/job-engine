# -*- coding: utf-8 -*-

import json
import logging
from collections import defaultdict
from nuvla.api import Api
from nuvla.api.util.filter import filter_or

from ..actions import action

action_name = 'create_deployment_set_old'

log = logging.getLogger(action_name)


def app_compatible_with_target(target_subtype, app_subtype):
    return (app_subtype == 'application_kubernetes' and target_subtype == 'infrastructure-service-kubernetes') or (
            app_subtype != 'application_kubernetes' and target_subtype != 'infrastructure-service-kubernetes')


def app_id(application):
    return application.split("_")[0]


def env_dict(env):
    d = defaultdict(dict)
    for el in env:
        d[el['application']][el['name']] = el['value']
    return d


def coupons_dict(coupons):
    d = {}
    for el in coupons:
        d[el['application']] = el['code']
    return d


@action(action_name, True)
class DeploymentSetCreateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.user_api = job.get_user_api()
        self.dep_set_id = self.job['target-resource']['href']
        self.deployment_set = self.user_api.get(self.dep_set_id).data
        spec = self.deployment_set['spec']
        self.targets = spec['targets']
        self.applications = spec['applications']
        self.start = spec['start']
        self.env_dict = env_dict(spec['env'])
        self.coupons_dict = coupons_dict(spec['coupons'])
        self.existing_deployments = self._load_existing_deployments()
        self.targets_info = self._load_targets_info()
        self.applications_info = self._load_applications_info()

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
        return self.user_api.add('deployment',
                                 {'module': {'href': application},
                                  'parent': target,
                                  'deployment-set': self.dep_set_id}).data['resource-id']

    def _update_env_deployment(self, deployment):
        env_app = self.env_dict.get(deployment['module']['id'])
        if env_app:
            for el in deployment['module']['content']['environmental-variables']:
                if el['name'] in env_app:
                    el['value'] = env_app[el['name']]

    def _update_coupon_deployment(self, deployment):
        coupon = self.coupons_dict.get(deployment['module']['id'])
        if coupon:
            deployment['coupon'] = coupon

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
                    deployment_id = self._create_deployment(target, application)
                    deployment = self.user_api.get(deployment_id).data
                    self._update_env_deployment(deployment)
                    self._update_coupon_deployment(deployment)
                    self.user_api.edit(deployment_id, deployment)
            progress += progress_increment
            self.job.set_progress(int(progress))
        self.user_api.edit(dep_set_id, {'state': 'CREATED'})
        if self.start:
            self.user_api.operation(self.user_api.get(dep_set_id), "start")
        return 0

    def do_work(self):
        return self._create()
