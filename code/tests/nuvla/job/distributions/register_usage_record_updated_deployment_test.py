#!/usr/bin/env python

import unittest
from unittest.mock import patch
from nuvla.job.distribution import DistributionBase
from nuvla.job.distributions.register_usage_record_updated_deployment import \
    RegisterUsageRecordUpdatedDeploymentJobsDistribution
from nuvla.api.models import CimiResource


class TestRegisterUsageRecordUpdatedDeploymentJobsDistribution(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.object(DistributionBase, '_start_distribution')
        self.mock_object = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_unique_owners(self):
        jd = RegisterUsageRecordUpdatedDeploymentJobsDistribution(None)

        self.assertEqual([], jd.unique_owners([]))

        user_a = "user/a"
        user_b = "user/b"
        group_c = "group/c"

        self.assertEqual([user_a, user_b], jd.unique_owners(
            [CimiResource({"owner": user_a}),
             CimiResource({"owner": user_b}),
             CimiResource({"owner": user_a})]))

        self.assertEqual([user_a, user_b, group_c], jd.unique_owners(
            [CimiResource({"owner": user_a}),
             CimiResource({"owner": user_b}),
             CimiResource({"owner": user_a}),
             CimiResource({"owner": group_c})]))

        self.assertEqual([user_a, user_b], jd.unique_owners(
            [CimiResource({"owner": user_a}),
             CimiResource({"owner": user_b}),
             CimiResource({"owner": user_a}),
             CimiResource({"owner": group_c,
                           "module": {"acl": {"edit-data": [group_c]}}})]))
