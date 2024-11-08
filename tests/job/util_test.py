#!/usr/bin/env python

import unittest

from nuvla.job_engine.job.util import status_message_from_exception, parse_version, version_smaller

class CustomException(Exception):
    pass


class TestJobUtil(unittest.TestCase):

    def test_status_message_from_exception(self):
        try: raise Exception('hello')
        except Exception:
            msg = status_message_from_exception()
        assert msg.startswith('Exception')
        assert msg.__contains__('hello')

    def test_status_message_from_custom_exception(self):
        try: raise CustomException('custom exception')
        except Exception:
            msg = status_message_from_exception()
        assert msg.startswith('CustomException')
        assert msg.__contains__('custom exception')

    def test_status_message_from_custom_exception_in_trycatch(self):
        try: raise CustomException('custom exception')
        except Exception: msg = status_message_from_exception()
        assert msg.startswith('CustomException')
        assert msg.__contains__('custom exception')

    def test_parse_version(self):
        assert parse_version('2.6.7') == (2, 6, 7)
        assert parse_version('0.1.90') == (0, 1, 90)
        assert parse_version('branch-name') is None

    def test_version_smaller(self):
        assert version_smaller('1.2.3', (2, 6, 7)) is True
        assert version_smaller('2.0.1', (2, 0, 2)) is True
        assert version_smaller('2.0.1', (2, 1, 2)) is True
        assert version_smaller('2.0.1', (2, 0, 0)) is False
        assert version_smaller('1.0.0', (1, 0, 0)) is False
        assert version_smaller('branch-name', (1, 0, 0)) is False
        assert version_smaller('branch-name', (100, 0, 0)) is False
