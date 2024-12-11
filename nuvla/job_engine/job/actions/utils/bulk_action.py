# -*- coding: utf-8 -*-
import abc
import json
import logging
from ...job import JOB_SUCCESS


class ActionException(Exception):
    def __init__(self, category, *args, **kwargs):
        super().__init__(category, args, kwargs)
        self.category = category
        self.resource_id = kwargs.get('resource_id')
        self.resource_name = kwargs.get('resource_name')
        self.message = kwargs.get('message')


class SkippedActionException(ActionException):
    def __init__(self, category, *args, **kwargs):
        super().__init__(category, *args, **kwargs)


class ActionCallException(ActionException):
    def __init__(self, category, *args, **kwargs):
        super().__init__(category, *args, **kwargs)
        self.context = kwargs.get('context')


class BulkActionResult:
    def __init__(self, actions_count: int):
        self._actions_count = actions_count
        self._failed_count = 0
        self._skipped_count = 0
        self._success = []
        self._queued = []
        self._running = []
        self._skip_reasons = {}
        self._fail_reasons = {}

    def add_success_action(self, resource_id):
        self._success.append(resource_id)

    def add_queued_action(self, resource_id):
        self._queued.append(resource_id)

    def set_queued_actions(self, queued:list):
        self._queued = queued

    def set_running_actions(self, running:list):
        self._running = running

    @staticmethod
    def _unsuccessful_action(entry, category, resource_id, resource_name, message=None):
        if category not in entry:
            entry[category] = {'COUNT': 0, 'IDS': {}}
        entry[category]['COUNT'] += 1
        if resource_id not in entry[category]['IDS']:
            entry[category]['IDS'][resource_id] = {'id': resource_id, 'COUNT': 0}
        entry[category]['IDS'][resource_id]['COUNT'] += 1
        if resource_name:
            entry[category]['IDS'][resource_id]['name'] = resource_name
        if message:
            entry[category]['IDS'][resource_id]['message'] = message

    def skip_action(self, category: str, resource_id='unknown', resource_name=None):
        self._skipped_count += 1
        self._unsuccessful_action(self._skip_reasons, category, resource_id, resource_name)

    def fail_action(self, category: str, resource_id='unknown', resource_name=None, message=None):
        self._failed_count += 1
        self._unsuccessful_action(self._fail_reasons, category, resource_id, resource_name, message)

    @staticmethod
    def _reasons_to_output_format(reasons):
        return [{
            'CATEGORY': category,
            'COUNT': cat_data['COUNT'],
            'IDS': sorted(cat_data['IDS'].values(), key=lambda d: d['COUNT'], reverse=True)}
            for category, cat_data in
            sorted(reasons.items(), key=lambda item: item[1]['COUNT'], reverse=True)]

    @staticmethod
    def _reasons_to_internal_format(reasons):
        reasons_internal_format = {}
        for reason in reasons:
            ids = {id_data['id']: id_data for id_data in reason.get('IDS', [])}
            reason['IDS'] = ids
            reasons_internal_format[reason['CATEGORY']] = reason
        return reasons_internal_format

    def to_dict(self):
        return {
            'ACTIONS_COUNT': self._actions_count,
            'FAILED_COUNT': self._failed_count,
            'SKIPPED_COUNT': self._skipped_count,
            'SUCCESS': self._success,
            'SUCCESS_COUNT': len(self._success),
            'QUEUED_COUNT': len(self._queued),
            'RUNNING_COUNT': len(self._running),
            'RUNNING': self._running,
            'QUEUED': self._queued,
            'SKIP_REASONS': self._reasons_to_output_format(self._skip_reasons),
            'FAIL_REASONS': self._reasons_to_output_format(self._fail_reasons),
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_string: str):
        data = json.loads(json_string)
        obj = cls(data.get("ACTIONS_COUNT", 0))
        obj._failed_count = data.get("FAILED_COUNT", 0)
        obj._skipped_count = data.get("SKIPPED_COUNT", 0)
        obj._success = data.get('SUCCESS', [])
        obj._queued = data.get("QUEUED", [])
        obj._running = data.get("RUNNING", [])
        obj._skip_reasons = cls._reasons_to_internal_format(data.get('SKIP_REASONS', []))
        obj._fail_reasons = cls._reasons_to_internal_format(data.get('FAIL_REASONS', []))
        return obj

class BulkAction(object):

    def __init__(self, job, action_name):
        self.job = job
        self.user_api = job.get_user_api()
        self.result = BulkActionResult(actions_count=0)
        self.todo = None
        self.progress = self.job.get('progress', 0)
        self.progress_increment = None
        self.action_name = action_name
        self._log = None

    def _push_result(self):
        self.job.set_status_message(self.result.to_json())

    def _set_progress_increment(self):
        if len(self.todo) > 0:
            self.progress_increment = 100 / len(self.todo)
        else:
            self.progress_increment = 0

    @abc.abstractmethod
    def get_todo(self):
        pass

    @abc.abstractmethod
    def action(self, todo_el):
        pass

    @property
    def log(self):
        if not self._log:
            self._log = logging.getLogger(self.action_name)
        return self._log

    def todo_resource_id(self, todo_el):
        return todo_el

    def try_action(self, todo_el):
        resource_id = self.todo_resource_id(todo_el)
        queued = False
        try:
            response = self.action(todo_el)
            status = response.data.get('status')
            if status == 202:
                self.result.set_queued_actions(resource_id)
                queued = True
            elif status == 200:
                self.result.add_success_action(resource_id)
            elif status == 201:
                resource_id = response.data.get('resource-id')
                self.result.add_success_action(resource_id)
            else:
                raise ActionCallException(f'Unexpected action response status {status}', context=todo_el)
        except SkippedActionException as ex:
            self.result.skip_action(ex.category, ex.resource_id, ex.resource_name)
            self.log.error(repr(ex))
        except ActionCallException as ex:
            self.result.fail_action(ex.category, ex.resource_id, ex.resource_name, ex.message)
            self.log.error(repr(ex))
        except Exception as ex:
            self.result.fail_action(str(ex), resource_id)
            self.log.error(repr(ex))
        if not queued:
            self.progress += self.progress_increment

    def bulk_operation(self):
        for todo_el in self.todo[:]:
            self.try_action(todo_el)
            self.job.update_job(status_message=self.result.to_json(),
                                progress=int(self.progress))

    def run(self):
        self.todo = self.get_todo()
        self.result = BulkActionResult(actions_count=len(self.todo))
        self._push_result()
        self._set_progress_increment()
        self.bulk_operation()
        if self.progress == 100:
            self.job.update_job(state=JOB_SUCCESS, return_code=0)
