# -*- coding: utf-8 -*-

import sys
import logging
import traceback

from requests.adapters import HTTPAdapter

from ..actions import get_action, ActionNotImplemented
from ..base import Base
from ..job import Job, JobUpdateError
from ..util import override, retry_kazoo_queue_op

CONNECTION_POOL_SIZE = 4


class LocalOneJobQueue(object):

    def __init__(self, job_id):
        self.job_id = job_id

    def get(self, *args, **kwargs):
        return self.job_id

    def noop(self):
        return True

    consume = noop
    release = noop


class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()

    def _get_action_instance(self, job):
        if 'action' not in job:
            raise Exception('Invalid job: {}.'.format(job))
        action_name = job.get('action')
        action = get_action(action_name)
        if not action:
            raise ActionNotImplemented(action_name)

        return action(self, job)

    def _set_command_specific_options(self, parser):
        parser.add_argument('--job-id', dest='job_id', metavar='ID',
                            help='Pull mode single job id to execute')

    def _process_jobs(self, queue):
        is_single_job_only = isinstance(queue, LocalOneJobQueue)
        api_http_adapter = HTTPAdapter(pool_maxsize=CONNECTION_POOL_SIZE,
                                       pool_connections=CONNECTION_POOL_SIZE)
        self.api.session.mount('http://', api_http_adapter)
        self.api.session.mount('https://', api_http_adapter)

        while not Executor.stop_event.is_set():
            job = Job(self.api, queue)

            if job.nothing_to_do:
                if is_single_job_only:
                    break
                else:
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
                if job.get('execution-mode', '').lower() == 'mixed':
                    status_message = 'Re-running job in pull mode after failed first attempt: ' \
                                     f'{status_message}'
                    job._edit_job_multi({'state': 'QUEUED',
                                         'status-message': status_message,
                                         'execution-mode': 'pull'})
                    retry_kazoo_queue_op(job.queue, 'consume')
                else:
                    job.update_job(state='FAILED', status_message=status_message, return_code=1)
                logging.error('Failed to process {}, with error: {}'.format(job.id, status_message))
            else:
                state = 'SUCCESS' if return_code == 0 else 'FAILED'
                job.update_job(state=state, return_code=return_code)
                logging.info('Finished {} with return_code {}.'.format(job.id, return_code))

            if is_single_job_only:
                break

        logging.info('Executor {} properly stopped.'.format(self.name))
        sys.exit(0)

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))

        job_id = self.args.job_id
        queue = LocalOneJobQueue(job_id) if job_id else self.kz.LockingQueue('/job')

        self._process_jobs(queue)