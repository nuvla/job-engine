# -*- coding: utf-8 -*-

from ..actions import action
from ...connector import nuvlabox as NB


@action('nuvlabox_cluster', True)
@action('nuvlabox_cluster_join_worker', True)
@action('nuvlabox_cluster_join_manager', True)
@action('nuvlabox_cluster_leave', True)
@action('nuvlabox_cluster_force_new_cluster', True)
class NBClusterJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def nuvlabox_cluster(self):
        nuvlabox_id = self.job['target-resource']['href']

        connector = NB.NuvlaBox(api=self.api, nuvlabox_id=nuvlabox_id, job=self.job)

        # IMPORTANT BIT THAT MUST CHANGE FOR EVERY NUVLABOX API ACTION

        r, e_code = connector.cluster_nuvlabox()

        self.job.update_job(status_message=r)
        #
        return e_code

    def do_work(self):
        return self.nuvlabox_cluster()
