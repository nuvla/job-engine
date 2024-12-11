#!/usr/bin/env python
import json
import unittest

from nuvla.job_engine.job.actions.utils.bulk_action import \
    BulkActionResult


class TestBulkActionResult(unittest.TestCase):

    def setUp(self):
        self.obj = BulkActionResult(actions_count=10)
        self.expected_obj = {'ACTIONS_COUNT': 10,
                             'FAILED_COUNT': 0,
                             'FAIL_REASONS': [],
                             'QUEUED': [],
                             'QUEUED_COUNT': 0,
                             'RUNNING': [],
                             'RUNNING_COUNT': 0,
                             'SKIPPED_COUNT': 0,
                             'SKIP_REASONS': [],
                             'SUCCESS': [],
                             'SUCCESS_COUNT': 0}

    def test_add_success_action(self):
        self.obj.add_success_action('nuvlabox/id-success-1')
        self.obj.add_success_action('nuvlabox/id-success-2')
        self.expected_obj['SUCCESS_COUNT'] = 2
        self.expected_obj['SUCCESS'] = ['nuvlabox/id-success-1', 'nuvlabox/id-success-2']
        self.assertEqual(self.expected_obj, self.obj.to_dict())

    def test_skip_action(self):
        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/a', resource_name='nuvlabox a')
        self.expected_obj['SKIPPED_COUNT'] = 1
        self.expected_obj['SKIP_REASONS'] = [{'CATEGORY': 'Offline Edges',
                                              'COUNT': 1,
                                              'IDS': [{'COUNT': 1,
                                                       'id': 'nuvlabox/a',
                                                       'name': 'nuvlabox a'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'nuvlabox/a count should be 1')

        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/b', resource_name='nuvlabox b')
        self.expected_obj['SKIPPED_COUNT'] = 2
        self.expected_obj['SKIP_REASONS'] = [{'CATEGORY': 'Offline Edges',
                                              'COUNT': 2,
                                              'IDS': [{'COUNT': 1,
                                                       'id': 'nuvlabox/a',
                                                       'name': 'nuvlabox a'},
                                                      {'COUNT': 1,
                                                       'id': 'nuvlabox/b',
                                                       'name': 'nuvlabox b'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'nuvlabox/b count should be 1')

        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/b', resource_name='nuvlabox b')
        self.expected_obj['SKIPPED_COUNT'] = 3
        self.expected_obj['SKIP_REASONS'] = [{'CATEGORY': 'Offline Edges',
                                              'COUNT': 3,
                                              'IDS': [{'COUNT': 2,
                                                       'id': 'nuvlabox/b',
                                                       'name': 'nuvlabox b'},
                                                      {'COUNT': 1,
                                                       'id': 'nuvlabox/a',
                                                       'name': 'nuvlabox a'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'nuvlabox/b count should be 2 and being sort as first in ids')

        self.obj.skip_action('Offline Edges')
        self.expected_obj['SKIPPED_COUNT'] = 4
        self.expected_obj['SKIP_REASONS'] = [{'CATEGORY': 'Offline Edges',
                                              'COUNT': 4,
                                              'IDS': [{'COUNT': 2,
                                                       'id': 'nuvlabox/b',
                                                       'name': 'nuvlabox b'},
                                                      {'COUNT': 1,
                                                       'id': 'nuvlabox/a',
                                                       'name': 'nuvlabox a'},
                                                      {'COUNT': 1,
                                                       'id': 'unknown'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(),
                         'unknown for skip without resource id, count should be 1')

        self.obj.skip_action('Configuration')
        self.expected_obj['SKIPPED_COUNT'] = 5
        self.expected_obj['SKIP_REASONS'] = [{'CATEGORY': 'Offline Edges',
                                              'COUNT': 4,
                                              'IDS': [{'COUNT': 2,
                                                       'id': 'nuvlabox/b',
                                                       'name': 'nuvlabox b'},
                                                      {'COUNT': 1,
                                                       'id': 'nuvlabox/a',
                                                       'name': 'nuvlabox a'},
                                                      {'COUNT': 1,
                                                       'id': 'unknown'}]},
                                             {'CATEGORY': 'Configuration',
                                              'COUNT': 1,
                                              'IDS': [{'COUNT': 1, 'id': 'unknown'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'new category is being added to skip and should be sorted')

    def test_fail_action(self):
        self.obj.fail_action('Some error', resource_id='deployment/a', message='some error detail')
        self.expected_obj['FAILED_COUNT'] = 1
        self.expected_obj['FAIL_REASONS'] = [{'CATEGORY': 'Some error',
                                              'COUNT': 1,
                                              'IDS': [{'COUNT': 1,
                                                       'id': 'deployment/a',
                                                       'message': 'some error detail'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict())

    def test_from_json(self):
        data = {
            'ACTIONS_COUNT': 21,
            'SUCCESS_COUNT': 1,
            'FAILED_COUNT': 3,
            'SKIPPED_COUNT': 14,
            'QUEUED_COUNT': 2,
            'RUNNING_COUNT': 1,
            'SUCCESS': ['deployment/s'],
            'QUEUED': ['deployment/y', 'deployment/z'],
            'RUNNING': ['deployment/x'],
            'SKIP_REASONS': [{
                'COUNT': 14,
                'CATEGORY': 'Offline Edges',
                'IDS': [
                    {
                        'id': 'nuvlabox/beta',
                        'name': 'ne-beta',
                        'COUNT': 12
                    },
                    {
                        'id': 'nuvlabox/alpha',
                        'name': 'ne-alpha',
                        'COUNT': 2
                    }
                ]
            }],
            'FAIL_REASONS': [{
                'CATEGORY': 'Error category foobar',
                'COUNT': 3,
                'IDS': [
                    {
                        'id': 'deployment/abc',
                        'name': 'ne-alpha',
                        'COUNT': 3
                    }
                ]
            }]
        }
        json_str = json.dumps(data)
        self.assertEqual(data, BulkActionResult.from_json(json_str).to_dict(), 'from data to json and back, data should be equal')

    def test_from_json_empty(self):
        BulkActionResult.from_json('{}')
