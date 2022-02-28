#!/usr/bin/env python

import unittest

from nuvla.connector.utils import remove_endpoint_protocol


class TestConnectorUtils(unittest.TestCase):

    def test_remove_endpoint_protocol(self):
        self.assertEqual('localhost',
                         remove_endpoint_protocol('https://localhost'))
        self.assertEqual('localhost',
                         remove_endpoint_protocol('http://localhost'))
        self.assertEqual('127.0.0.1',
                         remove_endpoint_protocol('http://127.0.0.1'))
        self.assertEqual('127.0.0.1',
                         remove_endpoint_protocol('http://127.0.0.1'))
        self.assertEqual('localhost',
                         remove_endpoint_protocol('localhost'))
