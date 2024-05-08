# -*- coding: utf-8 -*-

import argparse
import logging
import os
import random
import signal
import threading

from nuvla.api import Api
from requests.exceptions import ConnectionError
from statsd import StatsClient

STATSD_PORT = 8125

names = ['Cartman', 'Kenny', 'Stan', 'Kyle', 'Butters', 'Token', 'Timmy', 'Wendy', 'M. Garrison',
         'Chef', 'Randy', 'Ike', 'Mr. Mackey', 'Mr. Slave', 'Tweek', 'Craig']


class Base(object):
    stop_event = threading.Event()

    def __init__(self):
        self.args = None
        self._init_args_parser()
        self.kz: KazooClient = None
        self.api: Api = None
        self.name = None
        self.statsd: StatsClient = None

        arg_log_level = self.args.log_level
        env_log_level = os.getenv('JOB_LOG_LEVEL')
        log_level = env_log_level or arg_log_level
        self._init_logger(log_level)

        signal.signal(signal.SIGTERM, Base.on_exit)
        signal.signal(signal.SIGINT, Base.on_exit)

    def _init_args_parser(self):
        parser = argparse.ArgumentParser(description='Process Nuvla jobs')
        required_args = parser.add_argument_group('required named arguments')

        parser.add_argument(
            '--zk-hosts', dest='zk_hosts', default=None, nargs='+', metavar='HOST',
            help='ZooKeeper list of hosts [localhost:port]. (default: 127.0.0.1:2181)')

        parser.add_argument('--api-url', dest='api_url', default='https://nuvla.io', metavar='URL',
                            help='Nuvla endpoint to connect to (default: https://nuvla.io)')

        required_args.add_argument('--api-user', dest='api_user', help='Nuvla Username',
                                   metavar='USERNAME')
        required_args.add_argument('--api-pass', dest='api_pass', help='Nuvla Password',
                                   metavar='PASSWORD')

        required_args.add_argument('--api-key', dest='api_key', help='Nuvla API Key Id',
                                   metavar='API_KEY')
        required_args.add_argument('--api-secret', dest='api_secret', help='Nuvla API Key Secret',
                                   metavar='API_SECRET')

        parser.add_argument('--api-insecure', dest='api_insecure', default=False,
                            action='store_true',
                            help='Do not check Nuvla certificate')

        # NuvlaEdge fs is required here since version 2.14.0 because the shared directory changed. For the moment,
        # we are keeping the default value as /srv/nuvlaedge/shared. NuvlaEdge should pass the correct value
        parser.add_argument('--nuvlaedge-fs', dest='nuvlaedge_fs',
                            default='/srv/nuvlaedge/shared/',
                            help='NuvlaEdge data directory (default: /srv/nuvlaedge/shared)')

        parser.add_argument('--api-authn-header', dest='api_authn_header', default=None,
                            help='Set header for internal authentication')

        parser.add_argument('--name', dest='name', metavar='NAME', default=None,
                            help='Base name for this process')

        parser.add_argument('--statsd', dest='statsd', metavar='STATSD',
                            default=None, help=f'StatsD server as host[:{STATSD_PORT}].')

        parser.add_argument('-l', '--log-level', dest='log_level',
                            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                            default='INFO', help='Log level')

        parser.add_argument('-d', '--debug', dest='log_level',
                            action='store_const', const='DEBUG',
                            help='Set log level to debug')

        self._set_command_specific_options(parser)

        self.args = parser.parse_args()

    def _set_command_specific_options(self, parser):
        """Optional command line arguments to be added by subclasses if needed"""
        pass

    @staticmethod
    def _init_logger(log_level=None):
        log_format_str = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s'
        format_log = logging.Formatter(log_format_str)
        logger = logging.getLogger()
        logger.handlers[0].setFormatter(format_log)
        logger.setLevel(logging.INFO)
        logging.getLogger('nuvla').setLevel(logging.INFO)
        logging.getLogger('kazoo').setLevel(logging.WARN)
        logging.getLogger('urllib3').setLevel(logging.WARN)
        logging.getLogger('elasticsearch').setLevel(logging.WARN)

        if log_level:
            try:
                logger.setLevel(log_level)
            except Exception as e:
                logging.error(f'Failed to set log level to "{log_level}": {e}')

    def publish_metric(self, name, value):
        if self.statsd:
            self.statsd.gauge(name, value)
            logging.debug(f'published: {name} {value}')

    @staticmethod
    def on_exit(signum, frame):
        print('\n\nExecution interrupted by the user!')
        Base.stop_event.set()

    def do_work(self):
        raise NotImplementedError()

    def _init_kazoo(self):
        if self.args.zk_hosts:
            from kazoo.client import KazooClient, KazooRetry
            self.kz = KazooClient(','.join(self.args.zk_hosts),
                                  connection_retry=KazooRetry(max_tries=-1),
                                  command_retry=KazooRetry(max_tries=-1), timeout=30.0)
            self.kz.start()

    def _init_statsd(self):
        if self.args.statsd:
            statsd_hp = self.args.statsd.split(':')
            statsd_port = STATSD_PORT
            statsd_host = statsd_hp[0]
            if len(statsd_hp) > 1:
                statsd_port = statsd_hp[1]
            try:
                self.statsd = StatsClient(host=statsd_host,
                                          port=statsd_port,
                                          prefix=None,
                                          ipv6=False)
            except Exception as ex:
                logging.error(f'Failed to initialise StatsD client for {self.args.statsd}: {ex}')

    def _init_nuvla_api(self):
        # true unless header authentication is used
        reauthenticate = self.args.api_authn_header is None
        self.api = Api(endpoint=self.args.api_url, insecure=self.args.api_insecure,
                       persist_cookie=False, reauthenticate=reauthenticate,
                       authn_header=self.args.api_authn_header)
        try:
            if self.args.api_authn_header is None:
                if self.args.api_key and self.args.api_secret:
                    response = self.api.login_apikey(self.args.api_key, self.args.api_secret)
                else:
                    response = self.api.login_password(self.args.api_user, self.args.api_pass)
                if response.status_code == 403:
                    raise ConnectionError(
                        'Login with following user/apikey {} failed!'.format(self.args.api_user))
                # Uncomment following lines for manual remote test
                # session_id = self.api.current_session()
                # self.api.operation(self.api.get(session_id), 'switch-group',
                #                    {'claim': "group/nuvla-admin"})
        except ConnectionError as e:
            logging.error('Unable to connect to Nuvla endpoint {}! {}'.format(self.api.endpoint, e))
            exit(1)

    def execute(self):
        self.name = self.args.name if self.args.name is not None else names[
            int(random.uniform(1, len(names) - 1))]
        self._init_nuvla_api()
        self._init_kazoo()
        self._init_statsd()
        self.do_work()

        while True:
            signal.pause()


def main(command):
    try:
        command().execute()
    except Exception as e:
        logging.exception(e)
        exit(2)
