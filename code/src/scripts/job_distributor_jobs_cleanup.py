#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class CleanupJobsDistributor(Distributor):
    ACTION_NAME = 'cleanup_jobs'

    def __init__(self):
        super(CleanupJobsDistributor, self).__init__()
        self.collect_interval = 86400.0  # 1 day

    @override
    def job_generator(self):
        job = {'action': CleanupJobsDistributor.ACTION_NAME,
               'target-resource': {'href': 'job'}}
        yield job

    @override
    def _get_jobs_type(self):
        return CleanupJobsDistributor.ACTION_NAME


if __name__ == '__main__':
    main(CleanupJobsDistributor)
