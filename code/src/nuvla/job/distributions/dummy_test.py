# -*- coding: utf-8 -*-

from nuvla.job.util import override
from ..distributions import distribution
from .DistributionBase import DistributionBase


@distribution('dummy_test')
class DummyTestActionsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'dummy_test'

    def __init__(self, distributor):
        super(DummyTestActionsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 15.0  # 15s
        self._start_distribution()

