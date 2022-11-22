#!/usr/bin/env python

import unittest
from nuvla.job.actions.deployment_set_create \
    import app_compatible_with_target, env_dict, coupons_dict


class TestDeploymentSetCreate(unittest.TestCase):

    def test_app_compatible_with_target(self):
        self.assertTrue(app_compatible_with_target('infrastructure-service-kubernetes', 'application_kubernetes'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'component'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'application'))
        self.assertFalse(app_compatible_with_target('infrastructure-service-kubernetes', 'application'))

    def test_coupon_dict(self):
        self.assertEqual({}, coupons_dict([]))
        self.assertEqual({'module/a': 'a'}, coupons_dict([{'application': 'module/a',
                                                           'code': 'a'}]))
        self.assertEqual({'module/a': 'a',
                          'module/b': 'b'}, coupons_dict([{'application': 'module/a', 'code': 'a'},
                                                          {'application': 'module/b', 'code': 'b'}]))

    def test_env_dict(self):
        self.assertEqual({}, env_dict([]))
        self.assertEqual({'module/a': {'name_a': 'a'}}, dict(env_dict([{'application': 'module/a',
                                                                        'name': 'name_a',
                                                                        'value': 'a'}])))
        self.assertEqual({'module/a': {'name_a': 'a',
                                       'name_c': 'c'},
                          'module/b': {'name_b': 'b'}}, dict(env_dict([{'application': 'module/a',
                                                                        'name': 'name_a',
                                                                        'value': 'a'},
                                                                       {'application': 'module/b',
                                                                        'name': 'name_b',
                                                                        'value': 'b'},
                                                                       {'application': 'module/a',
                                                                        'name': 'name_c',
                                                                        'value': 'c'}])))
