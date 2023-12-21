# -*- coding: utf-8 -*-
import abc
import json


class BulkAction(object):
    FINAL_PROGRESS = 20

    def __init__(self, _, job):
        self.job = job
        self.user_api = job.get_user_api()
        self.result = {
            'bootstrap-exceptions': {},
            'FAILED': [],
            'SUCCESS': []}
        self.todo = None
        self.progress = self.job.get('progress', 0)
        self.progress_increment = None

    def _push_result(self):
        self.job.set_status_message(json.dumps(self.result))

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass

    def _set_progress_increment(self):
        progress_left = self.FINAL_PROGRESS - self.progress
        self.progress_increment = progress_left / len(self.todo)

    @abc.abstractmethod
    def get_todo(self):
        pass

    @abc.abstractmethod
    def action(self, todo_el):
        pass

    def bulk_operation(self):
        for todo_el in self.todo[:]:
            self.action(todo_el)
            self.progress += self.progress_increment
            self.job.set_progress(int(self.progress))

    def run(self):
        # Job recovery support
        if self.job.get('progress', 0) > 0:
            self.reload_result()
        if self.job.get('progress', 0) < self.FINAL_PROGRESS:
            self.todo = self.get_todo()
            self._set_progress_increment()
            self._push_result()
            self.bulk_operation()
            self.job.set_progress(self.FINAL_PROGRESS)
