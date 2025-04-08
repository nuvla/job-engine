# -*- coding: utf-8 -*-

import sys
import logging

from requests.adapters import HTTPAdapter

from .. import JobRetrievedInFinalState
from ..actions import get_action, ActionNotImplemented
from ..actions.utils.bulk_action import BulkAction
from ..base import Base
from ..job import Job, JobUpdateError, \
    JOB_FAILED, JOB_SUCCESS, JOB_QUEUED, JOB_RUNNING
from ..util import override, kazoo_check_processing_element, status_message_from_exception


CONNECTION_POOL_SIZE = 4


class LocalOneJobQueue(object):

    def __init__(self, job_id):
        self.processing_element = job_id

    def get(self, *args, **kwargs):
        return self.processing_element

    def noop(self):
        return True

    consume = noop
    release = noop


class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()

    def _set_command_specific_options(self, parser):
        parser.add_argument('--job-id', dest='job_id', metavar='ID',
                            help='Pull mode single job id to execute')

    @staticmethod
    def get_action_instance(job):
        if 'action' not in job:
            raise ValueError('Invalid job: {}.'.format(job))
        action_name = job.get('action')
        action = get_action(action_name)
        if not action:
            raise ActionNotImplemented(action_name)
        return action(job)

    @classmethod
    def process_job(cls, job):
        logging.info(f'Process job {job.id} with action {job.get("action")}.')
        try:
            action_instance = cls.get_action_instance(job)
            job.set_state(JOB_RUNNING)
            return_code = action_instance.do_work()
            state = JOB_SUCCESS if return_code == 0 else JOB_FAILED
            job.update_job(state=state, return_code=return_code)
            logging.info('Finished {} with return_code {}.'.format(job.id, return_code))
            if isinstance(action_instance, BulkAction):
                logging.info(f'Bulk job removed from queue {job.id}.')
            kazoo_check_processing_element(job.queue, 'consume')
        except ActionNotImplemented as e:
            logging.error('Action "{}" not implemented'.format(str(e)))
            msg = f'Not implemented action {job.id}'
            status_message = '{}: {}'.format(msg, str(e))
            job.update_job(state=JOB_FAILED, status_message=status_message)
            kazoo_check_processing_element(job.queue, 'consume')
        except JobRetrievedInFinalState as e:
            logging.warning(str(e))
            kazoo_check_processing_element(job.queue, 'consume')
        except JobUpdateError as e:
            logging.error(str(e))
            kazoo_check_processing_element(job.queue, 'release')
        except Exception:
            status_message = status_message_from_exception()
            if job.get('execution-mode', '').lower() == 'mixed':
                status_message = 'Re-running job in pull mode after failed first attempt: ' \
                                 f'{status_message}'
                job.update_job(state=JOB_QUEUED, status_message=status_message, execution_mode='pull')
            else:
                job.update_job(state=JOB_FAILED, status_message=status_message, return_code=1)
            logging.error(f'Failed to process {job.id}, with error: {status_message}')
            kazoo_check_processing_element(job.queue, 'consume')

    def _process_jobs(self, queue):
        is_single_job_only = isinstance(queue, LocalOneJobQueue)
        api_http_adapter = HTTPAdapter(pool_maxsize=CONNECTION_POOL_SIZE,
                                       pool_connections=CONNECTION_POOL_SIZE)
        self.api.session.mount('http://', api_http_adapter)
        self.api.session.mount('https://', api_http_adapter)

        while not Executor.stop_event.is_set():

            job = Job(self.api, queue, self.args.nuvlaedge_fs)

            if job.nothing_to_do:
                if is_single_job_only:
                    break
                else:
                    continue

            logging.info('Got new {}.'.format(job.id))

            self.process_job(job)

            if is_single_job_only:
                break

        logging.info(f'Executor {self.name} properly stopped.')
        sys.exit(0)

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))

        job_id = self.args.job_id
        queue = LocalOneJobQueue(job_id) if job_id else self.kz.LockingQueue('/job')

        self._process_jobs(queue)
