# -*- coding: utf-8 -*-

import logging

from ..actions import action
from ...connector.nuvlabox import NuvlaBox
from nuvla.api import NuvlaError


@action('disable-stream', True)
class NBDisableStreamJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def disable_stream(self):
        nuvlabox_peripheral_id = self.job['target-resource']['href']

        peripheral = None
        try:
            peripheral = self.api.get(nuvlabox_peripheral_id).data
        except NuvlaError as e:
            if e.response.status_code == 404:
                logging.warning(
                    "Peripheral has already been deleted. Will try to disable stream anyway")
            else:
                raise

        if peripheral:
            nuvlabox_id = peripheral['parent']
        else:
            # Peripheral has already been deleted
            try:
                nuvlabox_id = None
                for res in self.job['affected-resources']:
                    if res['href'].startswith("nuvlabox/"):
                        nuvlabox_id = res['href']
                        break
            except (IndexError, KeyError):
                logging.exception("Cannot figure out the corresponding NuvlaBox. Stopping")
                raise

        data = {"id": nuvlabox_peripheral_id}

        logging.info('Disabling data stream for {} in NuvlaBox {}'.format(nuvlabox_peripheral_id,
                                                                          nuvlabox_id))
        connector = NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        connector.start(api_action_name="data-source-mjpg/disable", method='post', payload=data)

        return 0

    def do_work(self):
        return self.disable_stream()
