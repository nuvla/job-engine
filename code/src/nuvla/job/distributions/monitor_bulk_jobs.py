# -*- coding: utf-8 -*-

import logging
from nuvla.api.util.filter import filter_and
from ..distributions import distribution
from ..distribution import DistributionBase
from ..util import override
from ..job import JOB_RUNNING, JOB_QUEUED


@distribution('monitor_bulk_jobs')
class MonitorBulkJobsDistributor(DistributionBase):
    DISTRIBUTION_NAME = 'monitor_bulk_job'

    def __init__(self, distributor):
        super(MonitorBulkJobsDistributor, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60
        self._start_distribution()

    def job_exists(self, job):
        jobs = self.distributor.api.search(
            'job',
            filter=filter_and(
                [f'state={[JOB_RUNNING, JOB_QUEUED]}',
                 f"action='{job['action']}'",
                 f"target-resource/href='{job['target-resource']['href']}'"]),
            last=0)
        return jobs.count > 0

    def get_bulk_jobs_running(self):
        filter_bulk_jobs = (f'action^="bulk" '
                            f'and state="{JOB_RUNNING}"'
                            f'and progress>=20')
        return self.distributor.api.search(
            'job',
            last=10000,
            select=['id'],
            filter=filter_bulk_jobs).resources

    def bulk_jobs_running(self):
        try:
            return [job.id for job in self.get_bulk_jobs_running()]
        except Exception as ex:
            logging.error(f'Failed to search for bulk jobs: {ex}')
            return []

    @override
    def job_generator(self):
        for job_id in self.bulk_jobs_running():
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': job_id}}
            if self.job_exists(job):
                continue
            yield job
