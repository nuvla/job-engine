# -*- coding: utf-8 -*-

import json
import logging

from ..actions import action
from nuvla.job_engine.connector import nuvlabox as NB


action_name = 'nuvlabox_scalability_start'

log = logging.getLogger(action_name)


@action(action_name)
class NuvlaBoxScalabilityStartJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_job_attributes(self):
        payload = json.loads(self.job.get('payload', '{}'))

        size = payload.get('size')
        module_id = payload.get('module-id')
        vpn_server_id = payload.get('vpn-server-id')
        release = payload.get('nuvlabox-release')
        credential_id = payload.get('credential-id')
        name_identifier = payload.get('name-identifier')

        if size is None or not module_id or not release or not credential_id or not name_identifier:
            raise Exception(f'The {action_name} job needs a payload with the following fields: '
                            f'size, module-id, vpn-server-id, nuvlabox-release, credential-id, name-identifier '
                            f'Payload provided: {payload}')

        return size, module_id, vpn_server_id, credential_id, \
               name_identifier, release, \
               payload.get('share-with', [])

    def start_scalability_test(self):
        size, module_id, vpn_server_id, credential_id, name_identifier, release, share_with = self.check_job_attributes()

        nb_connector = NB.NuvlaBox(api=self.api, job=self.job)

        nb_ids = nb_connector.create_nuvlaboxes(size, vpn_server_id, name_identifier, int(release.split('.')[0]), share_with)

        for id in nb_ids:
            depl = self.api.add('deployment', {'module': {'href': module_id}}).data

            depl_id = depl.get('resource-id')

            depl = self.api.get(depl_id).data
            depl['parent'] = credential_id
            depl['tags'] = [name_identifier]
            depl['module']['content']['environmental-variables'] = [
                {
                    "name": "NUVLABOX_ENGINE_VERSION",
                    "value": release
                },
                {
                    "name": "NUVLABOX_UUID",
                    "value": id
                }
            ]

            self.api.edit(depl_id, depl)

            self.api.get(depl_id + "/start")

        return 0

    def do_work(self):
        return self.start_scalability_test()
