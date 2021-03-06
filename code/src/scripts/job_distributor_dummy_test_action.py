#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
        job = {'action': self._get_jobs_type(),
               'target-resource': {'href': 'dummy'}}
        yield job

    @override
    def _get_jobs_type(self):
        return DummuTestActionsDistributor.ACTION_NAME


if __name__ == '__main__':
    main(DummuTestActionsDistributor)
