# -*- coding: utf-8 -*-

import logging
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('update_nuvlabox_online')
class NuvlaBoxStatusOfflineDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'update_nuvlabox_online'

    def __init__(self, distributor):
        super(NuvlaBoxStatusOfflineDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 30
        self._start_distribution()

    def collect_offline(self):
        filters = f"online = true and next-heartbeat < 'now'"
        select = 'id'
        last = 10000
        offline = self.distributor.api.search('nuvlabox-status', filter=filters, select=select, last=last)
        logging.info(f'Nuvlabox offline: {offline.count}')
        return offline.resources

    @override
    def job_generator(self):
        # we don't generate a job because it's a simple edit on each nuvlabox status
        for nuvlabox_status in self.collect_offline():
            self.distributor.api.edit(nuvlabox_status.id, {'online': False})
        return []
