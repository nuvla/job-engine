# -*- coding: utf-8 -*-

import sys
import logging

from concurrent.futures.thread import ThreadPoolExecutor
from ..base import Base
from ..distributions import get_distribution, distributions


class Distributor(Base):
    def __init__(self):
        super(Distributor, self).__init__()
        self.futures = {}

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

    def check_and_recreate_thread_on_exception(self, thread):
        for name, future in self.futures.items():
            try:
                ex = future.exception(timeout=1)
                if ex:
                    logging.error(f'Distributor {name} failed with: {repr(ex)}')
                    logging.warning(f'Restarting distributor {name}')
                    self.futures[name] = thread.submit(get_distribution(name), self)
            except TimeoutError:
                pass
            except Exception as ex:
                logging.error(f'Exception in distributor thread: {repr(ex)}')


    def do_work(self):
        logging.info('I am distributor {}.'.format(self.name))
        with ThreadPoolExecutor(max_workers=1000) as thread:
            for distribution_name in distributions:
                if distribution_name not in self.args.distribution_exclude:
                    self.futures[distribution_name] = thread.submit(get_distribution(distribution_name), self)
            while not self.stop_event.is_set():
                self.check_and_recreate_thread_on_exception(thread)
            thread.shutdown(wait=True)
        logging.info('Distributor properly stopped.')
        sys.exit(0)
