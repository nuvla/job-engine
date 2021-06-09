# -*- coding: utf-8 -*-

import sys
import logging

from concurrent.futures.thread import ThreadPoolExecutor
from ..base import Base
from ..distributions import get_distribution, distributions


class Distributor(Base):
    def __init__(self):
        super(Distributor, self).__init__()

    def _set_command_specific_options(self, parser):
        parser.add_argument(
            '--distribution-exclude', dest='distribution_exclude', default=[], nargs='+', metavar='DISTRIBUTION',
            help='List of distributions to exclude '
                 '(e.g. --distribution-exclude cleanup_jobs usage_report)')
        parser.add_argument(
            '--distribution-interval', dest='distribution_interval', default=[], nargs='+',
            metavar='DISTRIBUTION:INTERVAL',
            help='Configure distributions interval in seconds '
                 '(e.g. --distribution-interval usage_report:20 deployment_state_new:5)')

    def do_work(self):
        logging.info('I am distributor {}.'.format(self.name))
        with ThreadPoolExecutor(max_workers=1000) as thread:
            for distribution_name in distributions:
                if distribution_name not in self.args.distribution_exclude:
                    thread.submit(get_distribution(distribution_name), self)
            thread.shutdown(wait=True)
        logging.info('Distributor properly stopped.')
        sys.exit(0)
