# -*- coding: utf-8 -*-

import logging

from ..actions import action
from ...connector.nuvlabox import NuvlaBox


@action('restart-stream', True)
class NBRestartStreamJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def restart_stream(self):
        nuvlabox_peripheral_id = self.job['target-resource']['href']

        peripheral = self.api.get(nuvlabox_peripheral_id).data
        nuvlabox_id = peripheral['parent']

        data = {"id": nuvlabox_peripheral_id,
                "video-device": peripheral['video-device']}

        logging.info('Restarting data stream for {} in NuvlaBox {}'.format(nuvlabox_peripheral_id,
                                                                         nuvlabox_id))
        connector = NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        api_action_name = 'data-source-mjpg/restart'
        r = connector.start(api_action_name=api_action_name, method='post', payload=data)

        msg = 'Call /api/{} for NuvlaBox {}. Output: {}'.format(api_action_name, nuvlabox_id, r)
        self.job.set_status_message(msg)

        return 0

    def do_work(self):
        return self.restart_stream()
