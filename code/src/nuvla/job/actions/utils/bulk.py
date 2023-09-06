# -*- coding: utf-8 -*-

import json


class BulkJob(object):

    def __init__(self, _, job):
        self.job = job
        self.user_api = job.get_user_api()
        self.result = {
            'bootstrap-exceptions': {},
            'FAILED': [],
            'SUCCESS': [],
            'ALL': []}

    def _push_result(self):
        self.job.set_status_message(json.dumps(self.result))

    def resource_done(self):
        return set(self.result.get('SUCCESS', []) + self.result.get('FAILED', []))

    def resource_left(self):
        all_result = set(self.result.get('ALL', []))
        return all_result.difference(self.resource_done())

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass
