#!/usr/bin/env python

import unittest

from nuvla.connector.utils import remove_protocol_from_url, \
    extract_host_from_url


class TestConnectorUtils(unittest.TestCase):

    def test_remove_endpoint_protocol(self):
        self.assertEqual('localhost',
                         remove_protocol_from_url('https://localhost'))
        self.assertEqual('localhost',
                         remove_protocol_from_url('http://localhost'))
        self.assertEqual('127.0.0.1',
                         remove_protocol_from_url('http://127.0.0.1'))
        self.assertEqual('localhost:786/a?param=a',
                         remove_protocol_from_url(
                             'https://localhost:786/a?param=a'))
        self.assertEqual('localhost',
                         remove_protocol_from_url('localhost'))

    def test_extract_host_from_url(self):
        self.assertEqual('localhost',
                         extract_host_from_url(
                             'https://localhost:4656/hello?param=1'))
        self.assertEqual('localhost',
                         extract_host_from_url('http://localhost'))
        self.assertEqual('127.0.0.1',
                         extract_host_from_url('http://127.0.0.1'))
        self.assertEqual('localhost',
                         extract_host_from_url('localhost'))
