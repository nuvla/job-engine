# -*- coding: utf-8 -*-

from .DistributionBase import DistributionBase


class NuvlaBoxClusterCleanupDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'nuvlabox_cluster_cleanup'

    def __init__(self, distributor):
        super(NuvlaBoxClusterCleanupDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400.0  # 1 day
        self._start_distribution()
