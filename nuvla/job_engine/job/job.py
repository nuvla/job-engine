# -*- coding: utf-8 -*-

import json
import time
import logging
from nuvla.api import Api, NuvlaError, ConnectionError

from .version import Version, JobVersionNotYetSupported, JobVersionIsNoMoreSupported

log = logging.getLogger('job')

JOB_SUCCESS = 'SUCCESS'
JOB_QUEUED = 'QUEUED'
JOB_RUNNING = 'RUNNING'
JOB_FAILED = 'FAILED'
JOB_CANCELED = 'CANCELED'

STATES = (JOB_QUEUED, JOB_RUNNING, JOB_FAILED, JOB_SUCCESS, JOB_CANCELED)

class JobNotFoundError(Exception):
    pass

class JobUpdateError(Exception):
    pass

class JobRetrievedInFinalState(Exception):
    pass

class UnexpectedJobRetrieveError(Exception):
    pass

class Job(dict):

    def __init__(self, id, api, nuvlaedge_shared_path=None):
        super(Job, self).__init__()
        self.id = id
        self.cimi_job = None
        self.api = api
        self.nuvlaedge_shared_path = nuvlaedge_shared_path

        self._context = None
        self._payload = None

        self._init()

    def _init(self):
        try:
            self.cimi_job = self.get_cimi_job(self.id)
            dict.__init__(self, self.cimi_job.data)
            self._job_version_check()
            if self.is_in_final_state():
                log.warning(f'Retrieved {self.id} already in final state!')
                raise JobRetrievedInFinalState()
            elif self.get('state') == JOB_RUNNING:
                # could happen when updating job and cimi server is down!
                # let job actions decide what to do with it.
                log.warning('Newly retrieved {} in running state!'.format(self.id))
        except (JobNotFoundError,
                JobVersionNotYetSupported,
                JobVersionIsNoMoreSupported,
                JobRetrievedInFinalState) as e:
            raise e
        except Exception as e:
            logging.error(f'Fatal error when trying to retrieve {self.id}!: {repr(e)}')
            raise UnexpectedJobRetrieveError()

    def _job_version_check(self):
        job_version_str = str(self.get('version', '0'))
        try:
            Version.job_version_check(job_version_str)
        except JobVersionIsNoMoreSupported as e:
            msg = f"Job v{job_version_str} is not supported by Job engine v{Version.engine_version}"
            log.warning(msg)
            self.update_job(state=JOB_FAILED, status_message=msg)
            raise e
        except JobVersionNotYetSupported as e:
            log.debug(f"Job v{job_version_str} is higher than what support Job engine v{Version.engine_version}.")
            raise e

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
        logging.error(f'Retrieved {self.id} not found! Message: {reason}')
        raise JobNotFoundError()

    def is_in_final_state(self):
        return self.get('state') in (JOB_SUCCESS, JOB_FAILED, JOB_CANCELED)

    def set_progress(self, progress: int):
        self._edit_job('progress', progress)

    def set_status_message(self, status_message: str):
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

    def update_job(self, state=None, return_code=None, status_message=None, progress: int = None, execution_mode=None, tags=None):
        attributes = {}

        if state is not None:
            attributes['state'] = state

        if return_code is not None:
            attributes['return-code'] = return_code

        if status_message is not None:
            attributes['status-message'] = status_message

        if progress is not None:
            attributes['progress'] = progress

        if execution_mode is not None:
            attributes['execution-mode'] = execution_mode

        if tags is not None:
            attributes['tags'] = tags

        if attributes:
            self._edit_job_multi(attributes)

    def __edit(self, attributes):
        try:
            response = self.api.edit(self.id, attributes)
        except (NuvlaError, ConnectionError):
            logging.error(f'Failed to update following attributes "{attributes}" for {self.id}!')
            raise JobUpdateError()
        else:
            self.update(response.data)

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

    def get_api(self, authn_info):
        insecure = not self.api.session.verify
        return Api(endpoint=self.api.endpoint, insecure=insecure,
                   persist_cookie=False, reauthenticate=True,
                   authn_header=f'{authn_info["user-id"]} '
                                f'{authn_info["active-claim"]} '
                                f'{" ".join(authn_info["claims"])}')

    def get_user_api(self):
        authn_info = self.payload['authn-info']
        return self.get_api(authn_info)

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
