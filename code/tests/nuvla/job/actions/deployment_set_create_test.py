#!/usr/bin/env python

import unittest
from nuvla.job.actions.deployment_set_create_old \
    import app_compatible_with_target, env_dict, coupons_dict

module_a = 'module/a'
module_b = 'module/b'


class TestDeploymentSetCreate(unittest.TestCase):

    def test_app_compatible_with_target(self):
        self.assertTrue(app_compatible_with_target('infrastructure-service-kubernetes', 'application_kubernetes'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'component'))
        self.assertTrue(app_compatible_with_target('infrastructure-service-swarm', 'application'))
        self.assertFalse(app_compatible_with_target('infrastructure-service-kubernetes', 'application'))

    def test_coupon_dict(self):
        self.assertEqual({}, coupons_dict([]))
        self.assertEqual({module_a: 'a'}, coupons_dict([{'application': module_a,
                                                         'code': 'a'}]))
        self.assertEqual({module_a: 'a',
                          module_b: 'b'}, coupons_dict([{'application': module_a, 'code': 'a'},
                                                        {'application': module_b, 'code': 'b'}]))

    def test_env_dict(self):
        self.assertEqual({}, env_dict([]))
        self.assertEqual({module_a: {'name_a': 'a'}}, dict(env_dict([{'application': module_a,
                                                                      'name': 'name_a',
                                                                      'value': 'a'}])))
        self.assertEqual({module_a: {'name_a': 'a',
                                     'name_c': 'c'},
                          module_b: {'name_b': 'b'}}, dict(env_dict([{'application': module_a,
                                                                      'name': 'name_a',
                                                                      'value': 'a'},
                                                                     {'application': module_b,
                                                                      'name': 'name_b',
                                                                      'value': 'b'},
                                                                     {'application': module_a,
                                                                      'name': 'name_c',
                                                                      'value': 'c'}])))
