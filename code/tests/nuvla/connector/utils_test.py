#!/usr/bin/env python

import unittest

from nuvla.connector.utils import remove_endpoint_protocol


class TestConnectorUtils(unittest.TestCase):

    def test_remove_endpoint_protocol(self):
        self.assertEqual('localhost',
                         remove_endpoint_protocol('https://localhost'))
        self.assertEqual('localhost',
                         remove_endpoint_protocol('http://localhost'))
        self.assertEqual('1.2.3.4',
                         remove_endpoint_protocol('http://1.2.3.4'))
        self.assertEqual('1.2.3.4',
                         remove_endpoint_protocol('http://1.2.3.4://'))
        self.assertEqual('localhost',
                         remove_endpoint_protocol('localhost'))
