# -*- coding: utf-8 -*-

import logging

from nuvla.api.util.filter import filter_and
from ..job import JOB_QUEUED, JOB_RUNNING
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('deployment_set_automatic_update')
class DeploymentSetAutomaticUpdateJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'deployment_set_automatic_update'

    def __init__(self, distributor):
        super(DeploymentSetAutomaticUpdateJobsDistribution, self).__init__(
            self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60
        self._start_distribution()

    def auto_update_dgs(self):
        try:
            return self.distributor.api.search(
                'deployment-set',
                filter=filter_and(['state=["STARTED","UPDATED","PARTIALLY-STARTED","PARTIALLY-UPDATED"]',
                                   'auto-update=true',
                                   'next-refresh<="now"']),
                select='id',
                last=10000).resources
        except Exception as ex:
            logging.error(f'Failed to search for auto-update dgs: {ex}')
            return []

    def job_exists(self, job):
        jobs = self.distributor.api.search(
            'job',
            filter=filter_and(
                [f'state={[JOB_RUNNING, JOB_QUEUED]}',
                 f"action='{job['action']}'",
                 f"target-resource/href='{job['target-resource']['href']}'"]),
            last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        auto_update_dgs = self.auto_update_dgs()
        logging.info(f'Auto-update DGs count: {len(auto_update_dgs)}')
        for resource in auto_update_dgs:
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': resource.id}}
            if self.job_exists(job):
                continue
            yield job
