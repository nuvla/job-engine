# -*- coding: utf-8 -*-
import abc
import json
import logging


class BulkAction(object):
    FINAL_PROGRESS = 20
    RESULT_BOOTSTRAP_EXCEPTIONS = 'BOOTSTRAP_EXCEPTIONS'
    RESULT_RUNNING = 'RUNNING'
    RESULT_FAILED = 'FAILED'
    RESULT_SUCCESS = 'SUCCESS'
    RESULT_QUEUED = 'QUEUED'
    RESULT_ACTIONS_CALLED = 'ACTIONS_CALLED'
    RESULT_ACTIONS_COUNT = 'ACTIONS_COUNT'
    RESULT_JOBS_DONE = 'JOBS_DONE'
    RESULT_JOBS_COUNT = 'JOBS_COUNT'

    def __init__(self, job):
        self.job = job
        self.user_api = job.get_user_api()
        self.result = {
            self.RESULT_BOOTSTRAP_EXCEPTIONS: {},
            self.RESULT_FAILED: [],
            self.RESULT_SUCCESS: [],
            self.RESULT_QUEUED: [],
            self.RESULT_ACTIONS_CALLED: 0}
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

    def todo_resource_id(self, todo_el):
        return todo_el

    def try_action(self, todo_el):
        resource_id = self.todo_resource_id(todo_el)
        try:
            response = self.action(todo_el)
            status = response.data.get('status')
            if status == 202:
                self.result[self.RESULT_QUEUED].append(resource_id)
            elif status == 200:
                self.result[self.RESULT_SUCCESS].append(resource_id)
            elif status == 201:
                resource_id = response.data.get('resource-id')
                self.result[self.RESULT_SUCCESS].append(resource_id)
            else:
                logging.error(f'Unexpected status code {status}')
        except Exception as ex:
            if resource_id:
                self.result[self.RESULT_BOOTSTRAP_EXCEPTIONS][resource_id] = repr(ex)
                self.result[self.RESULT_FAILED].append(resource_id)

    def bulk_operation(self):
        for todo_el in self.todo[:]:
            self.try_action(todo_el)
            self.result[self.RESULT_ACTIONS_CALLED] += 1
            self.progress += self.progress_increment
            self.job.update_job(status_message=json.dumps(self.result),
                                progress=int(self.progress))

    def run(self):
        # Job recovery support
        if self.job.get('progress', 0) > 0:
            self.reload_result()
        if self.job.get('progress', 0) < self.FINAL_PROGRESS:
            self.todo = self.get_todo()
            self.result[self.RESULT_ACTIONS_COUNT] = len(self.todo)
            self._set_progress_increment()
            self._push_result()
            self.bulk_operation()
            self.job.set_progress(self.FINAL_PROGRESS)
