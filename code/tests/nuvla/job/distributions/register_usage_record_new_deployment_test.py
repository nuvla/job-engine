#!/usr/bin/env python

import unittest
from unittest.mock import MagicMock, patch
from nuvla.job.distribution import DistributionBase
from nuvla.job.distributions.register_usage_record_new_deployment import \
    RegisterUsageRecordNewDeploymentJobsDistribution


class TestDeploymentStateJobsDistributor(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.object(DistributionBase, '_start_distribution')
        self.mock_object = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_unique_owners(self):
        jd = RegisterUsageRecordNewDeploymentJobsDistribution(None)

        self.assertEqual([], jd.unique_owners([]))

        self.assertEqual(["user/a", "user/b"], jd.unique_owners(
            [{"owner": "user/a"},
             {"owner": "user/b"},
             {"owner": "user/a"}]))

        self.assertEqual(["user/a", "user/b", "group/c"], jd.unique_owners(
            [{"owner": "user/a"},
             {"owner": "user/b"},
             {"owner": "user/a"},
             {"owner": "group/c"}]))

        self.assertEqual(["user/a", "user/b"], jd.unique_owners(
            [{"owner": "user/a"},
             {"owner": "user/b"},
             {"owner": "user/a"},
             {"owner": "group/c",
              "module": {"acl": {"edit-data": ["group/c"]}}}]))
