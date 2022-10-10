#!/usr/bin/env python

import unittest
from nuvla.job.actions.deployment_set_create import app_compatible_with_target


class TestResourceLogFetchJob(unittest.TestCase):

    def test_app_compatible_with_target(self):
        self.assertTrue(app_compatible_with_target('infrastructure-service-kubernetes', 'application_kubernetes'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'component'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'application'))
        self.assertFalse(app_compatible_with_target('infrastructure-service-kubernetes', 'application'))
