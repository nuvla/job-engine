#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class NuvlaBoxReleasesDistributor(Distributor):
    ACTION_NAME = 'update_nuvlabox_releases'

    def __init__(self):
        super(NuvlaBoxReleasesDistributor, self).__init__()
        self.collect_interval = 30.0  # 1 day

    @override
    def job_generator(self):
        job = {'action': NuvlaBoxReleasesDistributor.ACTION_NAME,
               'target-resource': {'href': 'job'}}
        yield job

    @override
    def _get_jobs_type(self):
        return NuvlaBoxReleasesDistributor.ACTION_NAME


if __name__ == '__main__':
    main(NuvlaBoxReleasesDistributor)
