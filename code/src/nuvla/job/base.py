# -*- coding: utf-8 -*-

import argparse
import logging
import random
import signal
import threading

from kazoo.client import KazooClient, KazooRetry
from nuvla.api import Api
from requests.exceptions import ConnectionError

names = ['Cartman', 'Kenny', 'Stan', 'Kyle', 'Butters', 'Token', 'Timmy', 'Wendy', 'M. Garrison',
         'Chef', 'Randy', 'Ike', 'Mr. Mackey', 'Mr. Slave', 'Tweek', 'Craig']


class Base(object):
    stop_event = threading.Event()

    def __init__(self):
        self.args = None
        self._init_args_parser()
        self._kz = None
        self.api = None
        self.name = None

        self._init_logger()

        signal.signal(signal.SIGTERM, Base.on_exit)
        signal.signal(signal.SIGINT, Base.on_exit)

    def _init_args_parser(self):
        parser = argparse.ArgumentParser(description='Process Nuvla jobs')
        required_args = parser.add_argument_group('required named arguments')

        parser.add_argument(
            '--zk-hosts', dest='zk_hosts', default=['127.0.0.1:2181'], nargs='+', metavar='HOST',
            help='ZooKeeper list of hosts [localhost:port]. (default: 127.0.0.1:2181)')

        parser.add_argument('--api-url', dest='api_url', default='https://nuvla.io', metavar='URL',
                            help='Nuvla endpoint to connect to (default: https://nuvla.io)')

        required_args.add_argument('--api-user', dest='api_user', help='Nuvla username',
                                   metavar='USERNAME')
        required_args.add_argument('--api-pass', dest='api_pass', help='Nuvla Password',
                                   metavar='PASSWORD')

        parser.add_argument('--api-insecure', dest='api_insecure', default=False,
                            action='store_true',
                            help='Do not check Nuvla certificate')

        parser.add_argument('--api-authn-header', dest='api_authn_header', default=None,
                            help='Set header for internal authentication')

        parser.add_argument('--name', dest='name', metavar='NAME', default=None,
                            help='Base name for this process')

        self._set_command_specific_options(parser)

        self.args = parser.parse_args()

    def _set_command_specific_options(self, parser):
        pass

    @staticmethod
    def _init_logger():
        log_format_str = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s'
        format_log = logging.Formatter(log_format_str)
        logger = logging.getLogger()
        logger.handlers[0].setFormatter(format_log)
        logger.setLevel(logging.INFO)
        logging.getLogger('kazoo').setLevel(logging.WARN)
        logging.getLogger('elasticsearch').setLevel(logging.WARN)
        logging.getLogger('nuvla').setLevel(logging.INFO)
        logging.getLogger('urllib3').setLevel(logging.WARN)

    @staticmethod
    def on_exit(signum, frame):
        print('\n\nExecution interrupted by the user!')
        Base.stop_event.set()

    def do_work(self):
        raise NotImplementedError()

    def execute(self):
        self.name = self.args.name if self.args.name is not None else names[
            int(random.uniform(1, len(names) - 1))]

        # true unless header authentication is used
        reauthenticate = self.args.api_authn_header is None
        self.api = Api(endpoint=self.args.api_url, insecure=self.args.api_insecure,
                       reauthenticate=reauthenticate, authn_header=self.args.api_authn_header)
        try:
            if self.args.api_authn_header is None:
                response = self.api.login_password(self.args.api_user, self.args.api_pass)
                if response.status_code == 403:
                    raise ConnectionError(
                        'Login with following user {} failed!'.format(self.args.api_user))
        except ConnectionError as e:
            logging.error('Unable to connect to Nuvla endpoint {}! {}'.format(self.api.endpoint, e))
            exit(1)

        self._kz = KazooClient(','.join(self.args.zk_hosts),
                               connection_retry=KazooRetry(max_tries=-1),
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
