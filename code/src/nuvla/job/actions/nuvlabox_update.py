# -*- coding: utf-8 -*-

import logging,os

from ..actions import action
from nuvla.connector import nuvlabox_connector as NB


@action('nuvlabox_update')
class NBUpdateJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_api(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Updating NuvlaBox {}.'.format(nuvlabox_id))
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION
        # in this case, we need to fetch the target NB release
        affected_resources = self.job['affected-resources']
        nb_release_id = None
        for nbr in affected_resources:
            if nbr.get('href', '').startswith('nuvlabox-release/'):
                nb_release_id = nbr.get('href')
                break

        if nb_release_id:
            release = self.api.get(nb_release_id).data['release']
            r = connector.update(target_release=release)
        else:
            raise Exception('Cannot find any reference to an existing NuvlaBox target release')

        self.job.update_job(status_message=r)

        return 0

    def do_work(self):
        return self.check_api()
