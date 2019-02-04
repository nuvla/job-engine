#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import time
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class CleanupVmsDistributor(Distributor):
    ACTION_NAME = 'cleanup_virtual_machines'

    def __init__(self):
        super(CleanupVmsDistributor, self).__init__()
        self.collect_interval = 3600.0  # 1 hour

    @override
    def job_generator(self):
        while True:
            job = {'action': CleanupVmsDistributor.ACTION_NAME,
                   'targetResource': {'href': 'virtual-machine'}}
            yield job
            time.sleep(self.collect_interval)

    @override
    def _get_jobs_type(self):
        return 'cleanup_virtual_machines'


if __name__ == '__main__':
    main(CleanupVmsDistributor)
