# -*- coding: utf-8 -*-

import sys
import logging
from nuvla.api import Api

from .. import JobRetrievedInFinalState, UnexpectedJobRetrieveError
from ..actions import get_action, ActionNotImplemented
from ..actions.utils.bulk_action import UnfinishedBulkActionToMonitor
from ..base import Base
from ..job import Job, JobUpdateError, \
    JOB_FAILED, JOB_SUCCESS, JOB_QUEUED, JOB_RUNNING, JobNotFoundError, JobVersionNotYetSupported, \
    JobVersionIsNoMoreSupported
from ..util import override, kazoo_execute_action_if_needed, status_message_from_exception


class LocalOneJobQueue(object):

    def __init__(self, job_id):
        self.processing_element = job_id

    def get(self, *_args, **_kwargs):
        return self.processing_element.encode()

    @staticmethod
    def _stop():
        Base.stop_event.set()
        return True

    consume = _stop
    release = _stop

class ActionRunException(Exception):
    pass

class Executor(Base):
    def __init__(self):
        super(Executor, self).__init__()
        self.queue = None

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
    def try_action_run(job, action_instance):
        try:
            return action_instance.do_work()
        except UnfinishedBulkActionToMonitor as e:
            raise e
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

    @classmethod
    def process_job(cls, api: Api, queue, nuvlaedge_shared_path, job_id: str):
        try:
            logging.info('Got new {}.'.format(job_id))
            job = Job(job_id, api, nuvlaedge_shared_path)
            logging.info(f'Process {job_id} with action {job.get("action")}.')
            action_instance = cls.get_action_instance(job)
            job.set_state(JOB_RUNNING)
            return_code = cls.try_action_run(job, action_instance)
            state = JOB_SUCCESS if return_code == 0 else JOB_FAILED
            job.update_job(state=state, return_code=return_code)
            logging.info(f'Finished {job_id} with return_code {return_code}.')
            kazoo_execute_action_if_needed(queue, 'consume')
        except (ActionNotImplemented,
                JobRetrievedInFinalState,
                JobNotFoundError,
                JobVersionIsNoMoreSupported,
                ActionRunException,
                UnfinishedBulkActionToMonitor):
            kazoo_execute_action_if_needed(queue, 'consume')
        except (JobUpdateError,
                JobVersionNotYetSupported,
                UnexpectedJobRetrieveError):
            kazoo_execute_action_if_needed(queue, 'release')
        except Exception as e:
            logging.error(f'Unexpected exception occurred during process of {job_id}: {repr(e)}')
            kazoo_execute_action_if_needed(queue, 'consume')


    def process_jobs(self):
        while not Executor.stop_event.is_set():
            # queue timeout 5s to give a chance to exit the job executor
            # if no job is being received
            job_id =  self.queue.get(timeout=5)
            if job_id:
                self.process_job(self.api, self.queue, self.args.nuvlaedge_fs, job_id.decode())
        logging.info(f'Executor {self.name} properly stopped.')
        sys.exit(0)

    @override
    def do_work(self):
        logging.info('I am executor {}.'.format(self.name))
        job_id = self.args.job_id
        self.queue = LocalOneJobQueue(job_id) if job_id else self.kz.LockingQueue('/job')
        self.process_jobs()
