#!/usr/bin/env python

import unittest

from job_engine.job.distributions.deployment_state import DeploymentStateJobsDistribution


class TestDeploymentStateJobsDistributor(unittest.TestCase):

    def test_collect_zero_deployments(self):
        jd = DeploymentStateJobsDistribution('', None)

        self.assertEqual(0, len(list(jd.job_generator())))
