# -*- coding: utf-8 -*-

import sys
import logging

from nuvla.job.base import Base
from concurrent.futures.thread import ThreadPoolExecutor
from nuvla.job.distributions import get_distribution, distributions


class Distributor(Base):
    def __init__(self):
        super(Distributor, self).__init__()

    def _set_command_specific_options(self, parser):
        parser.add_argument(
            '--dist-exclude', dest='dist_exclude', default=None, nargs='+', metavar='DISTRIBUTOR',
            help='List of distributors to exclude (separated by space)')

    def do_work(self):
        logging.info('I am distributor {}.'.format(self.name))
        with ThreadPoolExecutor() as thread:
            for distribution_name in distributions:
                if distribution_name not in self.args.dist_exclude:
                    thread.submit(get_distribution(distribution_name), self)
            thread.shutdown(wait=True)
        logging.info('Distributor properly stopped.')
        sys.exit(0)
