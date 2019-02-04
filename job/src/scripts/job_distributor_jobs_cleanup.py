#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

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
        while True:
            job = {'action': CleanupJobsDistributor.ACTION_NAME,
                   'targetResource': {'href': 'job'}}
            yield job
            time.sleep(self.collect_interval)

    @override
    def _get_jobs_type(self):
        return 'cleanup_jobs'


if __name__ == '__main__':
    main(CleanupJobsDistributor)
