# -*- coding: utf-8 -*-

from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('update_nuvlabox_releases')
class NuvlaBoxReleasesDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'update_nuvlabox_releases'

    def __init__(self, distributor):
        super(NuvlaBoxReleasesDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400  # 1 day
        self._start_distribution()
