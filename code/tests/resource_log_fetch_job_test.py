#!/usr/bin/env python

import unittest
from unittest.mock import MagicMock, patch
import logging
from datetime import datetime, timezone

from nuvla.job.actions.resource_log_fetch import \
    ResourceLogFetchJob, \
    get_last_line_timestamp, \
    reduce_timestamp_precision, \
    last_timestamp_of_logs, \
    build_update_resource_log


class ImplementResourceLogFetchJob(ResourceLogFetchJob):

    @property
    def log(self):
        return logging.getLogger('')

    def all_components(self):
        return ['c1', 'c2']

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:
        return ''


class TestResourceLogFetchJob(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestResourceLogFetchJob, self).__init__(*args, **kwargs)
        self.line1 = '2022-02-15T15:56:58.194398728Z WARNING: line1'
        self.line2 = '2022-02-15T15:56:58.194398730Z ERROR: line2'
        self.date1 = '2022-02-15T15:56:58.194398728Z'
        self.date2 = '2022-02-15T15:56:58.194398730Z'
        self.date1_reduced = '2022-02-15T15:56:58.194Z'
        self.date2_reduced = '2022-02-15T15:56:58.194Z'

    def setUp(self) -> None:
        self.obj = ImplementResourceLogFetchJob('', MagicMock())

    def test_get_last_line_timestamp(self):
        self.assertIsNone(get_last_line_timestamp([]))
        self.assertIsNone(get_last_line_timestamp(None))
        self.assertEqual(
            self.date1,
            get_last_line_timestamp([self.line1]))
        self.assertEqual(
            self.date2, get_last_line_timestamp([self.line1,
                                                 self.line2]))

    def test_reduce_precision(self):
        self.assertIsNone(reduce_timestamp_precision(None))
        self.assertIsNone(reduce_timestamp_precision(''))
        self.assertEqual(
            self.date1_reduced,
            reduce_timestamp_precision(self.date1))

    def test_last_timestamp_of_logs(self):
        self.assertIsNone(last_timestamp_of_logs({'c1': []}))
        self.assertEqual(
            self.date1, last_timestamp_of_logs(
                {'c1': [self.line1]}))
        self.assertEqual(
            self.date2, last_timestamp_of_logs(
                {'c1': [self.line1],
                 'c2': [self.line1, self.line2]}))

    def test_build_update_resource_log(self):
        self.assertEqual(
            {'log': {'c1': []}}, build_update_resource_log({'c1': []}))
        self.assertEqual(
            {'last-timestamp': self.date1_reduced,
             'log': {'c1': [self.line1]}},
            build_update_resource_log({'c1': [self.line1]}))
        self.assertEqual(
            {'last-timestamp': self.date2_reduced,
             'log': {'c1': [self.line1],
                     'c2': [self.line1, self.line2]}},
            build_update_resource_log({'c1': [self.line1],
                                       'c2': [self.line1, self.line2]}))

    def test_all_components(self):
        self.assertEqual(['c1', 'c2'], self.obj.all_components())

    def test_get_since(self):
        self.obj.resource_log = {'since': self.date1_reduced}
        self.assertEqual(datetime(2022, 2, 15, 15, 56, 58, 194000,
                                  tzinfo=timezone.utc),
                         self.obj.get_since())
        self.obj.resource_log = {'since': self.date1_reduced,
                                 'last-timestamp': '2022-02-15T15:56:58.195Z'}

        self.assertEqual(datetime(2022, 2, 15, 15, 56, 58, 195000,
                                  tzinfo=timezone.utc),
                         self.obj.get_since())

    @patch.object(ImplementResourceLogFetchJob, 'fetch_resource_log')
    def test_do_work(self, mock_fetch_resource_log):
        self.obj.do_work()
        mock_fetch_resource_log.assert_called()

    @patch('nuvla.job.actions.resource_log_fetch.build_update_resource_log')
    @patch.object(ImplementResourceLogFetchJob, 'get_components_logs')
    @patch.object(ImplementResourceLogFetchJob, 'update_resource_log')
    def test_fetch_log(self,
                       mock_update_resource_log,
                       mock_get_components_logs,
                       mock_build_update_resource_log):
        mock_build_update_resource_log.return_value = {}
        self.obj.target_id = '1'
        self.obj.fetch_log()
        mock_get_components_logs.assert_called()
        mock_update_resource_log.assert_called_once_with('1', {})
