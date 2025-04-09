# -*- coding: utf-8 -*-

import sys
import logging
from requests.adapters import HTTPAdapter

from .. import JobRetrievedInFinalState, UnexpectedJobRetrieveError
from ..actions import get_action, ActionNotImplemented
from ..actions.utils.bulk_action import UnfinishedBulkActionToMonitor
from ..base import Base
from ..job import Job, JobUpdateError, \
    JOB_FAILED, JOB_SUCCESS, JOB_QUEUED, JOB_RUNNING, JobNotFoundError, JobVersionBiggerThanEngine, \
    JobVersionIsNoMoreSupported
from ..util import override, kazoo_check_processing_element, status_message_from_exception

CONNECTION_POOL_SIZE = 4


class LocalOneJobQueue(object):

    def __init__(self, job_id):
        self.processing_element = job_id

    def get(self, *_args, **_kwargs):
        return self.processing_element.encode()

    consume = Base.stop_event.set
    release = Base.stop_event.set

class ActionRunException(Exception):
    pass

class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()
        self.queue = None
        api_http_adapter = HTTPAdapter(pool_maxsize=CONNECTION_POOL_SIZE,
                                       pool_connections=CONNECTION_POOL_SIZE)
        self.api.session.mount('http://', api_http_adapter)
        self.api.session.mount('https://', api_http_adapter)

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
            msg = f'Not implemented action {job.id}: {action_name}'
            logging.error(msg)
            job.update_job(state=JOB_FAILED, status_message=msg)
            raise ActionNotImplemented()
        return action(job)

    @staticmethod
    def action_run(job, action_instance):
        try:
            return action_instance.do_work()
        except Exception:
            status_message = status_message_from_exception()
            if job.get('execution-mode', '').lower() == 'mixed':
                status_message = 'Re-running job in pull mode after failed first attempt: ' \
                                 f'{status_message}'
                job.update_job(state=JOB_QUEUED, status_message=status_message, execution_mode='pull')
            else:
                job.update_job(state=JOB_FAILED, status_message=status_message, return_code=1)
            logging.error(f'Failed to process {job.id}, with error: {status_message}')
            raise ActionRunException()

    def process_job(self):
        job_id = None
        try:
            job_id = self.queue.get(timeout=5).decode()
            logging.info('Got new {}.'.format(job_id))
            job = Job(job_id, self.api, self.args.nuvlaedge_fs)
            logging.info(f'Process job {job.id} with action {job.get("action")}.')
            action_instance = self.get_action_instance(job)
            job.set_state(JOB_RUNNING)
            return_code = action_instance.do_work()
            state = JOB_SUCCESS if return_code == 0 else JOB_FAILED
            job.update_job(state=state, return_code=return_code)
            logging.info(f'Finished {job_id} with return_code {return_code}.')
            kazoo_check_processing_element(self.queue, 'consume')
        except (ActionNotImplemented,
                JobRetrievedInFinalState,
                UnfinishedBulkActionToMonitor,
                JobNotFoundError,
                JobVersionIsNoMoreSupported,
                ActionRunException):
            kazoo_check_processing_element(self.queue, 'consume')
        except (JobUpdateError,
                JobVersionBiggerThanEngine,
                UnexpectedJobRetrieveError):
            kazoo_check_processing_element(self.queue, 'release')
        except Exception as e:
            logging.error(f'Unexpected exception occurred during process of {job_id}: {repr(e)}')
            kazoo_check_processing_element(self.queue, 'release')


    def _process_jobs(self):
        while not Executor.stop_event.is_set():
            self.process_job()
        logging.info(f'Executor {self.name} properly stopped.')
        sys.exit(0)

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))
        job_id = self.args.job_id
        self.queue = LocalOneJobQueue(job_id) if job_id else self.kz.LockingQueue('/job')
        self._process_jobs()
