#!/usr/bin/env python

import unittest

from nuvla.job.util import status_message_from_exception


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
