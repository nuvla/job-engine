# -*- coding: utf-8 -*-

import time
import logging
import re
import json

from nuvla.api import Api, NuvlaError, ConnectionError

from nuvla.job_engine.job.util import retry_kazoo_queue_op

from .version import version as engine_version

log = logging.getLogger('job')

VER_TRIM_RE = re.compile(r'\.?[^.0-9]+[0-9]*$')

JOB_SUCCESS = 'SUCCESS'
JOB_QUEUED = 'QUEUED'
JOB_RUNNING = 'RUNNING'
JOB_FAILED = 'FAILED'
JOB_CANCELED = 'CANCELED'

STATES = (JOB_QUEUED, JOB_RUNNING, JOB_FAILED, JOB_SUCCESS, JOB_CANCELED)


def version_to_tuple(ver: str) -> tuple:
    ver_ = list(map(int, VER_TRIM_RE.sub('', ver).split('.')))
    if len(ver_) < 2:
        return ver_[0], 0, 0
    return tuple(ver_)


class NonexistentJobError(Exception):
    def __init__(self, reason):
        super(NonexistentJobError, self).__init__(reason)
        self.reason = reason


class JobUpdateError(Exception):
    def __init__(self, reason):
        super(JobUpdateError, self).__init__(reason)
        self.reason = reason


class Job(dict):

    def __init__(self, api, queue, nuvlaedge_shared_path=None):
        super(Job, self).__init__()
        self.nothing_to_do = False
        self.id = None
        self.cimi_job = None
        self.queue = queue
        self.api = api
        self.nuvlaedge_shared_path = nuvlaedge_shared_path

        self._context = None
        self._payload = None
        self._engine_version = version_to_tuple(engine_version)
        if self._engine_version[0] < 2:
            self._engine_version_min = (0, 0, 1)
        elif self._engine_version[0] == 4:
            # For job-engine 4.x, we support jobs with version 2.x and 3.x
            self._engine_version_min = (self._engine_version[0] - 2, 0, 0)
        else:
            self._engine_version_min = (self._engine_version[0] - 1, 0, 0)
        self._init()

    def _init(self):
        try:
            self.id = self.queue.get(timeout=5)
            if self.id is None:
                self.nothing_to_do = True
            else:
                if isinstance(self.id, bytes):
                    self.id = self.id.decode()

                self.cimi_job = self.get_cimi_job(self.id)
                dict.__init__(self, self.cimi_job.data)
                self._job_version_check()
                if self.is_in_final_state():
                    retry_kazoo_queue_op(self.queue, 'consume')
                    log.warning('Newly retrieved {} already in final state! Removed from queue.'
                                .format(self.id))
                    self.nothing_to_do = True
                elif self.get('state') == JOB_RUNNING:
                    # could happen when updating job and cimi server is down!
                    # let job actions decide what to do with it.
                    log.warning('Newly retrieved {} in running state!'.format(self.id))
                self.is_bulk = self._is_bulk()
        except NonexistentJobError as e:
            retry_kazoo_queue_op(self.queue, 'consume')
            log.warning('Newly retrieved {} does not exist in cimi; '.format(self.id) +
                        'Message: {}; Removed from queue: success.'.format(e.reason))
            self.nothing_to_do = True
        except Exception as e:
            timeout = 30
            retry_kazoo_queue_op(self.queue, 'release')
            log.error(
                'Fatal error when trying to retrieve {}! Put it back in queue. '.format(self.id) +
                'Will go back to work after {}s.'.format(timeout))
            log.exception(e)
            time.sleep(timeout)
            self.nothing_to_do = True

    def _job_version_check(self):
        """Skips the job by setting `self.nothing_to_do = True` when the job's
        version is outside of the engine's supported closed range [M-1, M.m.P].
        Where M is major version from semantic version definition M.m.P.
        The job will be removed from the queue and set as failed if the job's
        version is strictly lower than M-1.
        The job will be skipped if its version is strictly greater engine's M.m.P.
        (This can happen for a short while during upgrades when jobs distribution
        gets upgraded before the job engine.)
        """
        job_version_str = str(self.get('version', '0.0.1'))
        job_version = version_to_tuple(job_version_str)
        if job_version < self._engine_version_min:
            evm_str = '.'.join(map(str, self._engine_version_min))
            msg = f"Job version {job_version_str} is smaller than min supported {evm_str}"
            log.warning(msg)
            retry_kazoo_queue_op(self.queue, 'consume')
            self.update_job(state=JOB_FAILED, status_message=msg)
            self.nothing_to_do = True
        elif job_version > self._engine_version:
            log.debug(f"Job version {job_version_str} is higher than engine's {engine_version}. "
                      "Putting job back to the queue.")
            retry_kazoo_queue_op(self.queue, 'release')
            self.nothing_to_do = True

    def get_cimi_job(self, job_uri):
        wait_time = 2
        max_attempt = 2
        reason = None
        for attempt in range(max_attempt):
            try:
                return self.api.get(job_uri)
            except NuvlaError as e:
                reason = e.reason
                if e.response.status_code == 404:
                    log.warning('Retrieve of {} failed. Attempt: {} Will retry in {}s.'
                                .format(job_uri, attempt, wait_time))
                    time.sleep(wait_time)
                else:
                    raise e
        raise NonexistentJobError(reason)

    def is_in_final_state(self):
        return self.get('state') in (JOB_SUCCESS, JOB_FAILED, JOB_CANCELED)

    def _is_bulk(self):
        return self.get('action', '').startswith("bulk")

    def set_progress(self, progress):
        if not isinstance(progress, int):
            raise TypeError('progress should be int not {}'.format(type(progress)))

        if not (0 <= progress <= 100):
            raise ValueError('progress should be between 0 and 100 not {}'.format(progress))

        self._edit_job('progress', progress)

    def set_status_message(self, status_message):
        if not status_message:
            status_message = '< status message empty >'
        self._edit_job('status-message', str(status_message))

    def set_return_code(self, return_code):
        if not isinstance(return_code, int):
            raise TypeError('return_code should be int not {}'.format(type(return_code)))

        self._edit_job('return-code', return_code)

    def set_state(self, state):
        if state not in STATES:
            raise ValueError(f'state should be one of {STATES}')

        self._edit_job('state', state)

    def _add_resources_to_list(self, field_name, resources_ids, href_format=True):
        has_to_update = False
        current_resources_ids = [resource['href'] if href_format else resource
                                 for resource in self.get(field_name, [])]

        for resource_id in resources_ids:
            if resource_id not in current_resources_ids:
                current_resources_ids.append(resource_id)
                has_to_update = True

        if has_to_update:
            field_data = [{'href': res_id} for res_id in current_resources_ids] \
                if href_format else current_resources_ids
            self._edit_job(field_name, field_data)

    def add_affected_resource(self, affected_resource):
        self._add_resources_to_list('affected-resources', [affected_resource])

    def add_affected_resources(self, affected_resources):
        self._add_resources_to_list('affected-resources', affected_resources)

    def add_nested_job(self, nested_job):
        self._add_resources_to_list('nested-jobs', [nested_job], False)

    def add_nested_jobs(self, nested_jobs):
        self._add_resources_to_list('nested-jobs', nested_jobs, False)

    def update_job(self, state=None, return_code=None, status_message=None):
        attributes = {}

        if state is not None:
            attributes['state'] = state

        if return_code is not None:
            attributes['return-code'] = return_code

        if status_message is not None:
            attributes['status-message'] = status_message

        if attributes:
            self._edit_job_multi(attributes)

    def consume_when_final_state(self):
        if self.is_in_final_state():
            retry_kazoo_queue_op(self.queue, 'consume')
            log.info('Reached final state: {} removed from queue.'.format(self.id))

    def __edit(self, attributes):
        try:
            response = self.api.edit(self.id, attributes)
        except (NuvlaError, ConnectionError):
            retry_kazoo_queue_op(self.queue, 'release')
            reason = 'Failed to update following attributes "{}" for {}! ' \
                     'Put it back in queue.'.format(attributes, self.id)
            raise JobUpdateError(reason)
        else:
            self.update(response.data)
            self.consume_when_final_state()

    def _edit_job(self, attribute_name, attribute_value):
        self.__edit({attribute_name: attribute_value})

    def _edit_job_multi(self, attributes):
        self.__edit(attributes)

    @property
    def context(self):
        if self._context is None:
            self._context = self.api.operation(self.cimi_job, 'get-context').data
        return self._context

    @property
    def is_in_pull_mode(self):
        return self.cimi_job.data.get('execution-mode', 'push') == 'pull'

    @property
    def payload(self):
        if self._payload is None and self.cimi_job.data.get('payload'):
            self._payload = json.loads(self.cimi_job.data['payload'])
        return self._payload

    def get_user_api(self):
        authn_info = self.payload['authn-info']
        insecure = not self.api.session.verify
        return Api(endpoint=self.api.endpoint, insecure=insecure,
                   persist_cookie=False, reauthenticate=True,
                   authn_header=f'{authn_info["user-id"]} '
                                f'{authn_info["active-claim"]} '
                                f'{" ".join(authn_info["claims"])}')

    @property
    def target_resource_href(self) -> str:
        """
        Returns a href to target-resource
        
        target-resource is not mandatory so this can fail with a KeyError
        """
        return self['target-resource']['href']

    def __setitem(self, key, value):
        dict.__setitem__(self, key, value)

    def __setitem__(self, key, value):
        raise TypeError(" '{}' does not support item assignment".format(self.__class__.__name__))

    def __delitem__(self, item):
        raise TypeError(" '{}' does not support item deletion".format(self.__class__.__name__))

    __getattr__ = dict.__getitem__
