# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
from elasticsearch import Elasticsearch
from requests.adapters import HTTPAdapter
from threading import Thread

from .actions import get_action, ActionNotImplemented
from .base import Base
from .job import Job, JobUpdateError
from .util import override


class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()
        self.es = None

    @override
    def _set_command_specific_options(self, parser):
        parser.add_argument('--threads', dest='number_of_thread', default=1,
                            metavar='#', type=int, help='Number of worker threads to start (default: 1)')
        parser.add_argument('--es-hosts-list', dest='es_hosts_list', default=['localhost'],
                            nargs='+', metavar='HOST', help='Elasticsearch list of hosts (default: [localhost])')

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
        api_http_adapter = HTTPAdapter(pool_maxsize=self.args.number_of_thread,
                                       pool_connections=self.args.number_of_thread)
        self.ss_api.session.mount('http://', api_http_adapter)
        self.ss_api.session.mount('https://', api_http_adapter)

        while not self.stop_event.is_set():
            job = Job(self.ss_api, queue)

            if job.nothing_to_do:
                continue

            logging.info('Got new {}.'.format(job.id))

            try:
                action_instance = self._get_action_instance(job)
                job.set_state('RUNNING')
                return_code = action_instance.do_work()
            except ActionNotImplemented as e:
                logging.exception('Action "{}" not implemented'.format(str(e)))
                # Consume not implemented action to avoid queue to be filled with not implemented actions
                msg = 'Not implemented action'.format(job.id)
                status_message = '{}: {}'.format(msg, str(e))
                job.update_job(state='FAILED', status_message=status_message)
            except JobUpdateError as e:
                logging.exception('{} update error: {}'.format(job.id, str(e)))
            except Exception as e:
                logging.exception('Failed to process {}.'.format(job.id))
                status_message = '{}'.format(str(e))
                job.update_job(state='FAILED', status_message=status_message)
            else:
                job.update_job(state='SUCCESS', return_code=return_code)
                logging.info('Successfully finished {}.'.format(job.id))
        logging.info('Thread properly stopped.')

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))
        self.es = Elasticsearch(self.args.es_hosts_list)
        for i in range(1, self.args.number_of_thread + 1):
            th_name = 'job_processor_{}_{}'.format(self.name, i)
            th = Thread(target=self._process_jobs, name=th_name)
            th.start()
