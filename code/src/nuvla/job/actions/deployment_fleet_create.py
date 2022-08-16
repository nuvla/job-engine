# -*- coding: utf-8 -*-

import json
import logging
from nuvla.api import Api

from ..actions import action

action_name = 'create_deployment_fleet'

log = logging.getLogger(action_name)


@action(action_name, True)
class DeploymentFleetCreateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = self.job.api
        self.user_api = self._get_user_api()

    def _get_user_api(self):
        authn_info = json.loads(self.job['payload'])['authn-info']
        insecure = not self.api.session.verify
        return Api(endpoint=self.api.endpoint, insecure=insecure,
                   persist_cookie=False, reauthenticate=True,
                   authn_header=f'{authn_info["user-id"]} '
                                f'{authn_info["active-claim"]} '
                                f'{" ".join(authn_info["claims"])}')

    def _existing_deployments(self, dep_fleet_id):
        query_result = self.user_api.search(
            'deployment',
            filter=f'deployment-fleet="{dep_fleet_id}"',
            last=10000,
            select='id, parent, module').resources
        return set([(r.data['parent'], r.data['module']['href'])
                    for r in query_result])

    def _create_deployment(self, dep_fleet_id, target, application):
        self.user_api.add('deployment',
                          {'module': {'href': application},
                           'parent': target,
                           'deployment-fleet': dep_fleet_id})

    def _update_progress(self):
        new_progress = 100 if self.progress_increment == 0 else int(
            100 - (len(self.monitored_jobs) / self.progress_increment))
        if new_progress != self.job['progress']:
            self.job.set_progress(new_progress)

    def _create(self):
        dep_fleet_id = self.job['target-resource']['href']
        log.info('Create {}.'.format(dep_fleet_id))
        deployment_fleet = self.user_api.get(dep_fleet_id).data
        targets = deployment_fleet['spec']['targets']
        applications = deployment_fleet['spec']['applications']
        progress = 10
        self.job.set_progress(progress)
        existing_deployments = self._existing_deployments(dep_fleet_id)
        progress_increment = 90 / len(targets)
        for target in targets:
            for application in applications:
                if (target, application) not in existing_deployments:
                    self._create_deployment(dep_fleet_id, target, application)
            progress += progress_increment
            self.job.set_progress(int(progress))
        self.user_api.edit(dep_fleet_id, {'state': 'CREATED'})
        return 0

    def do_work(self):
        return self._create()
