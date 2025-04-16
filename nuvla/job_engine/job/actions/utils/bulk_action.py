# -*- coding: utf-8 -*-
import abc
import json
import logging


class ActionException(Exception):
    def __init__(self, reason, *args, **kwargs):
        super().__init__(reason, args, kwargs)
        self.reason = reason
        self.resource_id = kwargs.get('resource_id')
        self.resource_name = kwargs.get('resource_name')
        self.message = kwargs.get('message')


class SkippedActionException(ActionException):
    def __init__(self, reason, *args, **kwargs):
        super().__init__(reason, *args, **kwargs)


class ActionCallException(ActionException):
    def __init__(self, reason, *args, **kwargs):
        super().__init__(reason, *args, **kwargs)
        self.context = kwargs.get('context')


class BulkActionResult:
    def __init__(self, actions_count: int):
        self._total_actions = actions_count
        self._failed_count = 0
        self._skipped_count = 0
        self._success = []
        self._queued = []
        self._running = []
        self._error_reasons = {}
        self._jobs_count = 0

    def add_success_action(self, resource_id):
        self._success.append(resource_id)

    def add_queued_action(self, resource_id):
        self._queued.append(resource_id)
        self._jobs_count += 1

    def set_queued_actions(self, queued: list):
        self._queued = queued

    def set_running_actions(self, running: list):
        self._running = running

    def exist_in_success(self, resource_id):
        return resource_id in self._success

    def exist_in_fail_reason_ids(self, reason, resource_id):
        return self._error_reasons.get(reason, {}).get('data', {}).get(resource_id) is not None

    def _unsuccessful_action(self, reason, category, resource_id, resource_name, message=None):
        if reason not in self._error_reasons:
            self._error_reasons[reason] = {'count': 0, 'data': {}, 'category': category}
        self._error_reasons[reason]['count'] += 1
        if resource_id not in self._error_reasons[reason]['data']:
            self._error_reasons[reason]['data'][resource_id] = {'id': resource_id, 'count': 0}
        self._error_reasons[reason]['data'][resource_id]['count'] += 1
        if resource_name:
            self._error_reasons[reason]['data'][resource_id]['name'] = resource_name
        if message:
            self._error_reasons[reason]['data'][resource_id]['message'] = message

    def skip_action(self, reason: str, resource_id='unknown', resource_name=None, message=None):
        self._skipped_count += 1
        self._unsuccessful_action(reason, 'skipped',  resource_id, resource_name, message)

    def fail_action(self, reason: str, resource_id='unknown', resource_name=None, message=None):
        self._failed_count += 1
        self._unsuccessful_action(reason, 'failed', resource_id, resource_name, message)

    @staticmethod
    def _error_reasons_to_output_format(reasons):
        return [{
            'reason': reason,
            'count': cat_data['count'],
            'category': cat_data['category'],
            'data': sorted(cat_data['data'].values(), key=lambda d: d['count'], reverse=True)}
            for reason, cat_data in
            sorted(reasons.items(), key=lambda item: item[1]['count'], reverse=True)]

    @staticmethod
    def _error_reasons_to_internal_format(reasons):
        reasons_internal_format = {}
        for reason in reasons:
            ids = {id_data['id']: id_data for id_data in reason.get('data', [])}
            reason['data'] = ids
            reasons_internal_format[reason['reason']] = reason
        return reasons_internal_format

    def to_dict(self):
        return {
            'total_actions': self._total_actions,
            'failed_count': self._failed_count,
            'skipped_count': self._skipped_count,
            'success': self._success,
            'success_count': len(self._success),
            'queued_count': len(self._queued),
            'running_count': len(self._running),
            'running': self._running,
            'queued': self._queued,
            'error_reasons': self._error_reasons_to_output_format(self._error_reasons),
            'jobs_count': self._jobs_count}

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_string: str):
        data = json.loads(json_string)
        obj = cls(data.get('total_actions', 0))
        obj._failed_count = data.get('failed_count', 0)
        obj._skipped_count = data.get('skipped_count', 0)
        obj._success = data.get('success', [])
        obj._queued = data.get('queued', [])
        obj._running = data.get('running', [])
        obj._jobs_count = data.get('jobs_count', 0)
        obj._error_reasons = cls._error_reasons_to_internal_format(data.get('error_reasons', []))
        return obj


class UnfinishedBulkActionToMonitor(Exception):
    pass

class BulkAction(object):
    monitor_tag = 'monitor'

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
                self.result.add_queued_action(resource_id)
                queued = True
            elif status == 200:
                self.result.add_success_action(resource_id)
            elif status == 201:
                resource_id = response.data.get('resource-id')
                self.result.add_success_action(resource_id)
            else:
                raise ActionCallException(f'Unexpected action response status {status}', context=todo_el)
        except SkippedActionException as ex:
            self.result.skip_action(ex.reason, ex.resource_id, ex.resource_name, ex.message)
            self.log.error(repr(ex))
        except ActionCallException as ex:
            self.result.fail_action(ex.reason, ex.resource_id, ex.resource_name, ex.message)
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

    def do_work(self):
        logging.info(f'Start {self.action_name} {self.job.id}')
        self.todo = self.get_todo()
        self.result = BulkActionResult(actions_count=len(self.todo))
        self._push_result()
        self._set_progress_increment()
        self.bulk_operation()
        if self.progress < 100:
            self.job.update_job(tags=[self.monitor_tag])
            self.log.info(f'Unfinished bulk action to monitor removed from queue {self.job.id}.')
            raise UnfinishedBulkActionToMonitor()
        logging.info(f'End of {self.action_name} {self.job.id}')
        return 0
