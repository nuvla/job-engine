# -*- coding: utf-8 -*-

from nuvla.job.distribution import DistributionBase


# @distribution('dummy_test')
class DummyTestActionsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'dummy_test'

    def __init__(self, distributor):
        super(DummyTestActionsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 15  # 15s
        self._start_distribution()

