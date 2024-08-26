# -*- coding: utf-8 -*-
import abc
from .bulk_action import BulkAction


class DeploymentBulkJob(BulkAction, abc.ABC):

    def __init__(self, job):
        super().__init__(job)

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
        return self.deployment_action(self.user_api.get(resource_id))
