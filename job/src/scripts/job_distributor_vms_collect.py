#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import time
import logging
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class CollectVmsDistributor(Distributor):
    ACTION_NAME = 'collect_virtual_machines'

    def __init__(self):
        super(CollectVmsDistributor, self).__init__()
        self.collect_interval = 60.0

    def _get_credentials(self):
        response = self.ss_api.cimi_search('credentials', select='id',
                                           filter='(type ^= "cloud-cred-") and (disabledMonitoring != true)')
        return response.resources_list

    @staticmethod
    def _time_spent(start_time):
        return time.time() - start_time

    def _time_left(self, start_time):
        return self.collect_interval - self._time_spent(start_time)

    @override
    def job_generator(self):
        while True:
            start_time = time.time()

            credentials = self._get_credentials()
            nb_credentials = len(credentials)

            yield_interval = float(self.collect_interval) / max(float(nb_credentials), 1) * 0.6

            for credential in credentials:
                pending_jobs = \
                    self.ss_api.cimi_search('jobs', filter='action="{}" and targetResource/href="{}" and state="QUEUED"'
                                            .format(CollectVmsDistributor.ACTION_NAME, credential.id), last=0)
                if pending_jobs.count == 0:
                    job = {'action': CollectVmsDistributor.ACTION_NAME,
                           'targetResource': {'href': credential.id}}
                    yield job
                else:
                    logging.debug('Action {} already queued, will not create a new job for {}.'
                                  .format(CollectVmsDistributor.ACTION_NAME, credential.id))

                time.sleep(yield_interval)
            time.sleep(self._time_left(start_time))

    @override
    def _get_jobs_type(self):
        return 'collect_virtual_machines'


if __name__ == '__main__':
    main(CollectVmsDistributor)
