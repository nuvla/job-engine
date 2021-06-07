# -*- coding: utf-8 -*-

from .DistributionBase import DistributionBase


class NuvlaBoxReleasesDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'update_nuvlabox_releases'

    def __init__(self, distributor):
        super(NuvlaBoxReleasesDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400.0  # 1 day
        self._start_distribution()
