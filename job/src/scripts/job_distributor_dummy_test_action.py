#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import time
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class DummuTestActionsDistributor(Distributor):
    ACTION_NAME = 'dummy_test_action'

    def __init__(self):
        super(DummuTestActionsDistributor, self).__init__()
        self.collect_interval = 15.0

    @override
    def job_generator(self):
        while True:
            job = {'action': DummuTestActionsDistributor.ACTION_NAME,
                   'targetResource': {'href': 'dummy'}}
            yield job
            time.sleep(self.collect_interval)

    @override
    def _get_jobs_type(self):
        return 'dummy_test_action'


if __name__ == '__main__':
    main(DummuTestActionsDistributor)
