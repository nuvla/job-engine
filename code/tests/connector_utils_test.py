#!/usr/bin/env python

import unittest

from nuvla.connector.utils import timestr2dtime, _time_rm_nanos


class TestConnectorUtils(unittest.TestCase):

    def test__time_rm_nanos(self):
        self.assertEqual(
            '2022-02-15T15:56:58.194Z',
            _time_rm_nanos('2022-02-15T15:56:58.194398728Z'))

    def test_timestr2dtime(self):
        self.assertEqual(
            None, timestr2dtime(
        '2022-02-15T15:56:58.194398728Z'))
