#!/usr/bin/env python
# -*- coding: utf-8 -*-

from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class VulnerabilitiesDatabaseDistributor(Distributor):
    ACTION_NAME = 'update_vulnerabilities_database'

    def __init__(self):
        super(VulnerabilitiesDatabaseDistributor, self).__init__()
        self.collect_interval = 86 #400.0  # 1 day

    @override
    def job_generator(self):
        job = {'action': VulnerabilitiesDatabaseDistributor.ACTION_NAME,
               'target-resource': {'href': 'job'}}
        yield job

    @override
    def _get_jobs_type(self):
        return VulnerabilitiesDatabaseDistributor.ACTION_NAME


if __name__ == '__main__':
    main(VulnerabilitiesDatabaseDistributor)
