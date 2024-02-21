# -*- coding: utf-8 -*-
import abc
from .bulk_action import BulkAction


class DeploymentBulkJob(BulkAction, abc.ABC):

    def __init__(self, _, job):
        super().__init__(_, job)

    def get_todo(self):
        return [deployment.id
                for deployment in
                self.user_api.search('deployment',
                                     filter=self.job.payload['filter'],
                                     select='id').resources]

    @abc.abstractmethod
    def deployment_action(self, deployment):
        pass

    def action(self, resource_id):
        try:
            return self.deployment_action(self.user_api.get(resource_id))
        except Exception as ex:
            self.result['bootstrap-exceptions'][resource_id] = repr(ex)
            self.result['FAILED'].append(resource_id)
            self._push_result()
