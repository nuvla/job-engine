# -*- coding: utf-8 -*-
import abc
from .bulk_action import BulkAction


class NuvlaboxBulkJob(BulkAction, abc.ABC):

    def __init__(self, job):
        super().__init__(job)

    def get_todo(self):
        return [ne.id
                for ne in
                self.user_api.search('nuvlabox',
                                     filter=self.job.payload['filter'],
                                     select='id').resources]

    @abc.abstractmethod
    def nuvlabox_action(self, nuvlabox):
        pass

    def action(self, resource_id):
        try:
            return self.nuvlabox_action(self.user_api.get(resource_id))
        except Exception as ex:
            self.result['bootstrap-exceptions'][resource_id] = repr(ex)
            self.result['FAILED'].append(resource_id)
            self._push_result()
