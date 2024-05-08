# -*- coding: utf-8 -*-

import os
import logging

from ..actions import action
from ...connector import nuvlabox as NB
from ...connector.kubernetes import K8sEdgeMgmt
from ...job.job import Job

@action('nuvlabox_update', True)
class NBUpdateJob(object):

    def __init__(self, _, job: Job):
        self.job = job
        self.api = job.api

    def nuvlabox_update(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('Updating NuvlaBox {}'.format(nuvlabox_id))
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            logging.debug('Found kubernetes installation.')
            connector = K8sEdgeMgmt(self.job)
        else:
            logging.info('Found docker installation.')
            connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)
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
            r, e_code = connector.update_nuvlabox_engine(target_release=release)
        else:
            raise Exception('Cannot find any reference to an existing NuvlaBox target release')

        self.job.update_job(status_message=r)

        return e_code
    
    def do_work(self):
        return self.nuvlabox_update()
