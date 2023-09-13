# -*- coding: utf-8 -*-

from abc import ABC

from .bulk_action import BulkAction


class DeploymentBulkJob(BulkAction, ABC):

    def __init__(self, _, job):
        super().__init__(_, job)

    def get_resources_ids(self):
        return [deployment.id
                for deployment in
                self.user_api.search('deployment',
                                     filter=self.job.payload['filter'],
                                     select='id').resources]
