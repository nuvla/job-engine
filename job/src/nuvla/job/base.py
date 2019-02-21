# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import logging
import random
import sys
import threading
import signal
from functools import partial
from kazoo.client import KazooClient, KazooRetry
from nuvla.api import Api

names = ['Cartman', 'Kenny', 'Stan', 'Kyle', 'Butters', 'Token', 'Timmy', 'Wendy', 'M. Garrison', 'Chef',
         'Randy', 'Ike', 'Mr. Mackey', 'Mr. Slave', 'Tweek', 'Craig']


class Base(object):
    def __init__(self):
        self.args = None
        self._init_args_parser()
        self._kz = None
        self.api = None
        self.name = None
        self.stop_event = threading.Event()

        self._init_logger()

        signal.signal(signal.SIGTERM, partial(Base.on_exit, self.stop_event))
        signal.signal(signal.SIGINT, partial(Base.on_exit, self.stop_event))

    def _init_args_parser(self):
        parser = argparse.ArgumentParser(description='Process Nuvla jobs')
        required_args = parser.add_argument_group('required named arguments')

        parser.add_argument('--zk-hosts', dest='zk_hosts', default=['127.0.0.1:2181'], nargs='+', metavar='HOST',
                            help='ZooKeeper list of hosts [localhost:port]. (default: 127.0.0.1:2181)')

        parser.add_argument('--api-url', dest='api_url',
                            help='Nuvla endpoint to connect to (default: https://nuvla.io)',
                            default='https://nuvla.io', metavar='URL')

        required_args.add_argument('--api-user', dest='api_user', help='Nuvla username',
                                   metavar='USERNAME', required=True)
        required_args.add_argument('--api-pass', dest='api_pass', help='Nuvla Password',
                                   metavar='PASSWORD', required=True)

        parser.add_argument('--api-insecure', dest='api_insecure', default=False, action='store_true',
                            help='Do not check Nuvla certificate')

        parser.add_argument('--name', dest='name', metavar='NAME', default=None, help='Base name for this process')

        self._set_command_specific_options(parser)

        self.args = parser.parse_args()

    def _set_command_specific_options(self, parser):
        pass

    @staticmethod
    def _init_logger():
        format_log = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - '
                                       '%(filename)s:%(lineno)s - %(message)s')
        logger = logging.getLogger()
        logger.handlers[0].setFormatter(format_log)
        logger.setLevel(logging.INFO)
        logging.getLogger('kazoo').setLevel(logging.WARN)
        logging.getLogger('elasticsearch').setLevel(logging.WARN)
        logging.getLogger('nuvla').setLevel(logging.INFO)
        logging.getLogger('urllib3').setLevel(logging.WARN)

    @staticmethod
    def on_exit(stop_event, signum, frame):
        print('\n\nExecution interrupted by the user!')
        stop_event.set()
        sys.exit(0)

    def do_work(self):
        raise NotImplementedError()

    def execute(self):
        self.name = self.args.name if self.args.name is not None else names[int(random.uniform(1, len(names) - 1))]

        self.api = Api(endpoint=self.args.api_url, insecure=self.args.api_insecure, reauthenticate=True)
        self.api.login_internal(self.args.api_user, self.args.api_pass)

        self._kz = KazooClient(','.join(self.args.zk_hosts), connection_retry=KazooRetry(max_tries=-1),
                               command_retry=KazooRetry(max_tries=-1), timeout=30.0)
        self._kz.start()

        self.do_work()

        while True:
            signal.pause()


def main(command):
    try:
        command().execute()
    except Exception as e:
        logging.exception(e)
        exit(2)
