# -*- coding: utf-8 -*-

from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('cleanup_jobs')
class CleanupJobsDistributor(DistributionBase):
    DISTRIBUTION_NAME = 'cleanup_jobs'

    def __init__(self, distributor):
        super(CleanupJobsDistributor, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 86400  # 1 day
        self._start_distribution()

