# -*- coding: utf-8 -*-

import logging
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('nuvlabox_offline')
class NuvlaBoxOfflineDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'nuvlabox_offline'

    def __init__(self, distributor):
        super(NuvlaBoxOfflineDistribution, self).__init__(
            self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 30
        self._start_distribution()

    def collect_offline(self):
        filters = "online = true and next-heartbeat < 'now'"
        select = 'id, state'
        last = 10000
        offline = self.distributor.api.search('nuvlabox', filter=filters,
                                              select=select, last=last)
        logging.info(f'Nuvlabox offline: {offline.count}')
        return offline.resources

    def set_offline(self, nuvlabox):
        try:
            self.distributor.api.operation(nuvlabox, 'set-offline')
        except Exception as ex:
            logging.error(f'Failed edit {nuvlabox.id} to set offline : {ex}')

    @override
    def job_generator(self):
        # we don't generate a job because it's a simple edit of nuvlabox status
        for nuvlabox in self.collect_offline():
            self.set_offline(nuvlabox)
        return []
