#!/usr/bin/env python

import unittest

from nuvla.api import Api as Nuvla
from nuvla.job.distributions.deployment_state import DeploymentStateJobsDistribution


class TestDeploymentStateJobsDistributor(unittest.TestCase):

    def test_collect_deployments(self):
        jd = DeploymentStateJobsDistribution('')

        jd.api = Nuvla()
        jd.api.login_password('super', 'supeR8-supeR8')

        jd.collect_interval = 60
        print('collect_interval: {0}, to process: {1}'.format(
            jd.collect_interval, len(list(jd.job_generator()))))

        print(':::' * 6)

        jd.collect_interval = 10
        print('collect_interval: {0}, to process: {1}'.format(
            jd.collect_interval, len(list(jd.job_generator()))))

