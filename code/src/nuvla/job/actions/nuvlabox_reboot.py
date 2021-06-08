# -*- coding: utf-8 -*-

import logging

from ..actions import action
from ...connector import nuvlabox_connector as NB


@action('reboot_nuvlabox', True)
class NBRebootJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def reboot(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Rebooting NuvlaBox {}.'.format(nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        r = connector.reboot()

        return 0

    def do_work(self):
        return self.reboot()
