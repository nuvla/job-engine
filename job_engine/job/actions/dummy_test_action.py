# -*- coding: utf-8 -*-

from ..util import random_wait
from ..actions import action


@action('dummy_test_action')
class DummyTestActionJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    @staticmethod
    def work_hard():
        random_wait(3, 30)

    def do_work(self):
        self.work_hard()
        return 0
