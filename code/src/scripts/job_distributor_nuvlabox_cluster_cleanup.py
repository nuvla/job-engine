#!/usr/bin/env python
# -*- coding: utf-8 -*-

from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class NuvlaBoxClusterCleanupDistributor(Distributor):
    ACTION_NAME = 'nuvlabox_cluster_cleanup'

    def __init__(self):
        super(NuvlaBoxClusterCleanupDistributor, self).__init__()
        self.collect_interval = 86400.0  # 1 day
        self.exit_on_failure = True

    @override
    def job_generator(self):
        job = {'action': NuvlaBoxClusterCleanupDistributor.ACTION_NAME,
               'target-resource': {'href': 'job'}}
        yield job

    @override
    def _get_jobs_type(self):
        return NuvlaBoxClusterCleanupDistributor.ACTION_NAME


if __name__ == '__main__':
    main(NuvlaBoxClusterCleanupDistributor)
