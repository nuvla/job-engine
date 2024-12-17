#!/usr/bin/env python
import json
import unittest

from nuvla.job_engine.job.actions.utils.bulk_action import \
    BulkActionResult


class TestBulkActionResult(unittest.TestCase):

    def setUp(self):
        self.obj = BulkActionResult(actions_count=10)
        self.expected_obj = {'total_actions': 10,
                             'failed_count': 0,
                             'error_reasons': [],
                             'queued': [],
                             'queued_count': 0,
                             'running': [],
                             'running_count': 0,
                             'skipped_count': 0,
                             'success': [],
                             'success_count': 0,
                             'jobs_count': 0}

    def test_add_success_action(self):
        self.obj.add_success_action('nuvlabox/id-success-1')
        self.obj.add_success_action('nuvlabox/id-success-2')
        self.expected_obj['success_count'] = 2
        self.expected_obj['success'] = ['nuvlabox/id-success-1', 'nuvlabox/id-success-2']
        self.assertEqual(self.expected_obj, self.obj.to_dict())

    def test_skip_action(self):
        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/a', resource_name='nuvlabox a')
        self.expected_obj['skipped_count'] = 1
        self.expected_obj['error_reasons'] = [{'reason': 'Offline Edges',
                                               'count': 1,
                                               'category': 'skipped',
                                               'data': [{'count': 1,
                                                         'id': 'nuvlabox/a',
                                                         'name': 'nuvlabox a'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'nuvlabox/a count should be 1')

        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/b', resource_name='nuvlabox b')
        self.expected_obj['skipped_count'] = 2
        self.expected_obj['error_reasons'] = [{'reason': 'Offline Edges',
                                               'count': 2,
                                               'category': 'skipped',
                                               'data': [{'count': 1,
                                                         'id': 'nuvlabox/a',
                                                         'name': 'nuvlabox a'},
                                                        {'count': 1,
                                                         'id': 'nuvlabox/b',
                                                         'name': 'nuvlabox b'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(), 'nuvlabox/b count should be 1')

        self.obj.skip_action('Offline Edges', resource_id='nuvlabox/b', resource_name='nuvlabox b')
        self.expected_obj['skipped_count'] = 3
        self.expected_obj['error_reasons'] = [{'reason': 'Offline Edges',
                                               'count': 3,
                                               'category': 'skipped',
                                               'data': [{'count': 2,
                                                         'id': 'nuvlabox/b',
                                                         'name': 'nuvlabox b'},
                                                        {'count': 1,
                                                         'id': 'nuvlabox/a',
                                                         'name': 'nuvlabox a'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(),
                         'nuvlabox/b count should be 2 and being sort as first in ids')

        self.obj.skip_action('Offline Edges')
        self.expected_obj['skipped_count'] = 4
        self.expected_obj['error_reasons'] = [{'reason': 'Offline Edges',
                                               'count': 4,
                                               'category': 'skipped',
                                               'data': [{'count': 2,
                                                         'id': 'nuvlabox/b',
                                                         'name': 'nuvlabox b'},
                                                        {'count': 1,
                                                         'id': 'nuvlabox/a',
                                                         'name': 'nuvlabox a'},
                                                        {'count': 1,
                                                         'id': 'unknown'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(),
                         'unknown for skip without resource id, count should be 1')

        self.obj.skip_action('Configuration')
        self.expected_obj['skipped_count'] = 5
        self.expected_obj['error_reasons'] = [{'reason': 'Offline Edges',
                                               'count': 4,
                                               'category': 'skipped',
                                               'data': [{'count': 2,
                                                         'id': 'nuvlabox/b',
                                                         'name': 'nuvlabox b'},
                                                        {'count': 1,
                                                         'id': 'nuvlabox/a',
                                                         'name': 'nuvlabox a'},
                                                        {'count': 1,
                                                         'id': 'unknown'}]},
                                              {'reason': 'Configuration',
                                               'category': 'skipped',
                                               'count': 1,
                                               'data': [{'count': 1, 'id': 'unknown'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict(),
                         'new reason is being added to error reasons as skipped and should be sorted')

    def test_fail_action(self):
        self.obj.fail_action('Some error', resource_id='deployment/a', message='some error detail')
        self.expected_obj['failed_count'] = 1
        self.expected_obj['error_reasons'] = [{'reason': 'Some error',
                                               'count': 1,
                                               'category': 'failed',
                                               'data': [{'count': 1,
                                                         'id': 'deployment/a',
                                                         'message': 'some error detail'}]}]
        self.assertEqual(self.expected_obj, self.obj.to_dict())

    def test_exist_in_fail_reason_ids(self):
        self.assertFalse(self.obj.exist_in_fail_reason_ids('Job failed', 'deployment/a'))
        self.obj.fail_action('Job failed', resource_id='deployment/a', message='some error detail')
        self.assertTrue(self.obj.exist_in_fail_reason_ids('Job failed', 'deployment/a'))
        self.assertFalse(self.obj.exist_in_fail_reason_ids('Job failed', 'deployment/b'))
        self.obj.fail_action('Job failed', resource_id='deployment/b', message='some error detail')
        self.assertTrue(self.obj.exist_in_fail_reason_ids('Job failed', 'deployment/b'))

    def test_exist_in_success(self):
        self.assertFalse(self.obj.exist_in_success('deployment/a'))
        self.obj.add_success_action('deployment/a')
        self.assertTrue(self.obj.exist_in_success('deployment/a'))

    def test_from_json(self):
        data = {
            'total_actions': 21,
            'success_count': 1,
            'failed_count': 3,
            'skipped_count': 14,
            'queued_count': 2,
            'running_count': 1,
            'success': ['deployment/s'],
            'queued': ['deployment/y', 'deployment/z'],
            'running': ['deployment/x'],
            'jobs_count': 4,
            'error_reasons': [{
                'count': 14,
                'reason': 'Offline Edges',
                'category': 'skipped',
                'data': [
                    {
                        'id': 'nuvlabox/beta',
                        'name': 'ne-beta',
                        'count': 12
                    },
                    {
                        'id': 'nuvlabox/alpha',
                        'name': 'ne-alpha',
                        'count': 2
                    }
                ]
            },
                {
                    'reason': 'Error reason foobar',
                    'count': 3,
                    'category': 'failed',
                    'data': [
                        {
                            'id': 'deployment/abc',
                            'name': 'ne-alpha',
                            'count': 3
                        }
                    ]
                }]
        }
        json_str = json.dumps(data)
        print(json_str)
        self.assertEqual(data, BulkActionResult.from_json(json_str).to_dict(),
                         'from data to json and back, data should be equal')

    def test_from_json_empty(self):
        BulkActionResult.from_json('{}')
