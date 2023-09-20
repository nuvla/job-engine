# -*- coding: utf-8 -*-
import abc
import json


class BulkAction(object):

    def __init__(self, _, job):
        self.job = job
        self.user_api = job.get_user_api()
        self.result = {
            'bootstrap-exceptions': {},
            'FAILED': [],
            'SUCCESS': [],
            'TODO': []}

    def _push_result(self):
        self.job.set_status_message(json.dumps(self.result))

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass

    @abc.abstractmethod
    def get_todo(self):
        pass

    @abc.abstractmethod
    def bulk_operation(self):
        pass

    def run(self):
        # Job recovery support
        if self.job.get('progress', 0) > 0:
            self.reload_result()
        if self.job.get('progress', 0) < 10:
            self.result['TODO'] = self.get_todo()
            self._push_result()
            self.job.set_progress(10)
        if self.job.get('progress', 0) < 20:
            self.bulk_operation()
            self.job.set_progress(20)
