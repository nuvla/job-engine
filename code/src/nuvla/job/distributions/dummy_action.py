# -*- coding: utf-8 -*-

from ..distribution import DistributionBase


# @distribution('dummy_action')
class DummyTestActionsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'dummy_action'

    def __init__(self, distributor):
        super(DummyTestActionsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 15  # 15s
        self._start_distribution()

