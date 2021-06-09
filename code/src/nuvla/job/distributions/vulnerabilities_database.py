# -*- coding: utf-8 -*-

from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('update_vulnerabilities_database')
class VulnerabilitiesDatabaseDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'update_vulnerabilities_database'

    def __init__(self, distributor):
        super(VulnerabilitiesDatabaseDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400  # 1 day
        self._start_distribution()
