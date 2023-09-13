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
            'TO_DO': []}

    def _push_result(self):
        self.job.set_status_message(json.dumps(self.result))

    def reload_result(self):
        try:
            self.result = json.loads(self.job.get('status-message'))
        except Exception:
            pass

    @abc.abstractmethod
    def get_resources_ids(self):
        pass

    @abc.abstractmethod
    def action(self, resource):
        pass

    def bulk_operation(self):
        for resource_id in self.result['TO_DO']:
            try:
                self.action(self.user_api.get(resource_id))
                self.result['TO_DO'].remove(resource_id)
            except Exception as ex:
                self.result['bootstrap-exceptions'][resource_id] = repr(ex)
                self.result['FAILED'].append(resource_id)
            self._push_result()

    def run(self):
        # Job recovery support
        if self.job.get('progress', 0) > 0:
            self.reload_result()
        if self.job.get('progress', 0) < 10:
            self.result['TO_DO'] = self.get_resources_ids()
            self._push_result()
            self.job.set_progress(10)
        if self.job.get('progress', 0) < 20:
            self.bulk_operation()
            self.job.set_progress(20)
