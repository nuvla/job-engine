# -*- coding: utf-8 -*-

from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('nuvlabox_cluster_cleanup')
class NuvlaBoxClusterCleanupDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'nuvlabox_cluster_cleanup'

    def __init__(self, distributor):
        super(NuvlaBoxClusterCleanupDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400  # 1 day
        self._start_distribution()
