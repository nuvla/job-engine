# -*- coding: utf-8 -*-

from ..distributions import distribution
from ..distribution import DistributionBase
from ..util import override
from ..job import JOB_RUNNING
import logging


@distribution('bulk_jobs_monitor')
class BulkJobsMonitorDistributor(DistributionBase):
    DISTRIBUTION_NAME = 'bulk_jobs_monitor'

    def __init__(self, distributor):
        super(BulkJobsMonitorDistributor, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60  # 1 min
        self._start_distribution()

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
            yield {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': job_id}}
