# -*- coding: utf-8 -*-

import sys
import logging
import traceback

from elasticsearch import Elasticsearch
from requests.adapters import HTTPAdapter

from .actions import get_action, ActionNotImplemented
from .base import Base
from .job import Job, JobUpdateError
from .util import override

CONNECTION_POOL_SIZE = 4


class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()
        self.es = None

    @override
    def _set_command_specific_options(self, parser):
        parser.add_argument(
            '--es-hosts', dest='es_hosts', default=['localhost'], nargs='+', metavar='HOST',
            help='Elasticsearch list of hosts [localhost:[port]] (default: [localhost])')

    def _get_action_instance(self, job):
        if 'action' not in job:
            raise Exception('Invalid job: {}.'.format(job))
        action_name = job.get('action')
        action = get_action(action_name)
        if not action:
            raise ActionNotImplemented(action_name)

        return action(self, job)

    def _process_jobs(self):
        queue = self._kz.LockingQueue('/job')
        api_http_adapter = HTTPAdapter(pool_maxsize=CONNECTION_POOL_SIZE,
                                       pool_connections=CONNECTION_POOL_SIZE)
        self.api.session.mount('http://', api_http_adapter)
        self.api.session.mount('https://', api_http_adapter)

        while not Executor.stop_event.is_set():
            job = Job(self.api, queue)

            if job.nothing_to_do:
                continue

            logging.info('Got new {}.'.format(job.id))

            try:
                action_instance = self._get_action_instance(job)
                job.set_state('RUNNING')
                return_code = action_instance.do_work()
            except ActionNotImplemented as e:
                logging.error('Action "{}" not implemented'.format(str(e)))
                # Consume not implemented action to avoid queue
                # to be filled with not implemented actions
                msg = 'Not implemented action'.format(job.id)
                status_message = '{}: {}'.format(msg, str(e))
                job.update_job(state='FAILED', status_message=status_message)
            except JobUpdateError as e:
                logging.error('{} update error: {}'.format(job.id, str(e)))
            except Exception as ex:
                ex_type, ex_msg, ex_tb = sys.exc_info()
                status_message = type(ex).__name__ + '-' + ''.join(traceback.format_exception(
                    etype=ex_type, value=ex_msg, tb=ex_tb))
                logging.error('Failed to process {}, with error: {}'.format(job.id, status_message))
                job.update_job(state='FAILED', status_message=status_message)
            else:
                state = 'SUCCESS' if return_code == 0 else 'FAILED'
                job.update_job(state=state, return_code=return_code)
                logging.info('Finished {} with return_code {}.'.format(job.id, return_code))
        logging.info('Executor {} properly stopped.'.format(self.name))
        sys.exit(0)

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))
        self.es = Elasticsearch(self.args.es_hosts)
        self._process_jobs()
