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
        return self.nuvlabox_action(self.user_api.get(resource_id))
