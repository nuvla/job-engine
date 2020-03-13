# -*- coding: utf-8 -*-

import logging

from ..actions import action
from nuvla.connector import nuvlabox_connector as NB


@action('enable-stream')
class NBEnableStreamJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def enable_stream(self):
        nuvlabox_peripheral_id = self.job['target-resource']['href']

        peripheral = self.api.get(nuvlabox_peripheral_id).json()
        nuvlabox_id = peripheral['parent']

        data = {
            "id": nuvlabox_peripheral_id,
            "video-device": peripheral['video-device']
        }

        logging.info('Enabling data stream for {} in NuvlaBox {}'.format(nuvlabox_peripheral_id, nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        r = connector.start(api_action_name="data-source-mjpg/enable", method='post', payload=data)

        return 0

    def do_work(self):
        return self.enable_stream()
