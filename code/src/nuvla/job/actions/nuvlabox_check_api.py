# -*- coding: utf-8 -*-

import logging,os

from ..actions import action
from nuvla.connector import nuvlabox_connector as NB


@action('check_nuvlabox_api')
class NBCheckJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_api(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Checking API for NuvlaBox {}.'.format(nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        r = connector.start(method='get')

        return 0

    def do_work(self):
        return self.check_api()
