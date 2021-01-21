#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class NuvlaBoxStatusOfflineDistributor(Distributor):
    ACTION_NAME = 'update_nuvlabox_online'

    def __init__(self):
        super(NuvlaBoxStatusOfflineDistributor, self).__init__()
        self.collect_interval = 30

    @override
    def _get_jobs_type(self):
        return NuvlaBoxStatusOfflineDistributor.ACTION_NAME

    def collect_offline(self):
        filters = f"online = true and next-heartbeat < 'now'"
        select = 'id'
        last = 10000
        offline = self.api.search('nuvlabox-status', filter=filters, select=select, last=last)
        logging.info(f'Nuvlabox offline: {offline.count}')
        return offline.resources

    @override
    def job_generator(self):
        # we don't generate a job because it's a simple edit on each nuvlabox status
        for nuvlabox_status in self.collect_offline():
            self.api.edit(nuvlabox_status.id, {'online': False})


if __name__ == '__main__':
    main(NuvlaBoxStatusOfflineDistributor)
