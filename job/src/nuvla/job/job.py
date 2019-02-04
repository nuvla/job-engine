# -*- coding: utf-8 -*-

from __future__ import print_function

from nuvla.api import NuvlaError, ConnectionError

from .util import wait, retry_kazoo_queue_op

import logging


class NonexistentJobError(Exception):
    def __init__(self, reason):
        super(NonexistentJobError, self).__init__(reason)
        self.reason = reason


class JobUpdateError(Exception):
    def __init__(self, reason):
        super(JobUpdateError, self).__init__(reason)
        self.reason = reason


class Job(dict):

    def __init__(self, ss_api, queue):
        self.nothing_to_do = False
        self.id = None
        self.queue = queue
        self.ss_api = ss_api
        try:
            self.id = queue.get()
            cimi_job = self.get_cimi_job(self.id)
            dict.__init__(self, cimi_job)
            if self.is_in_final_state():
                retry_kazoo_queue_op(queue, "consume")
                logging.warning('Newly retrieved {} already in final state! Removed from queue.'.format(self.id))
                self.nothing_to_do = True
            elif self.get('state') == 'RUNNING':
                # could happen when updating job and cimi server is down! let job actions decide what to do with it.
                logging.warning('Newly retrieved {} in running state!'.format(self.id))
        except NonexistentJobError as e:
            retry_kazoo_queue_op(queue, "consume")
            logging.warning('Newly retrieved {} does not exist in cimi; '.format(self.id) +
                            'Message: {}; Removed from queue: success.'.format(e.reason))
            self.nothing_to_do = True
        except:
            timeout = 120
            retry_kazoo_queue_op(queue, "release")
            logging.exception('Fatal error when trying to retrieve {}! Put it back in queue. '.format(self.id) +
                              'Will go back to work after {}s.'.format(timeout))
            wait(timeout)
            self.nothing_to_do = True

    def get_cimi_job(self, job_uri):
        wait_time = 2
        max_attempt = 2
        reason = None
        for attempt in range(max_attempt):
            try:
                return self.ss_api.cimi_get(job_uri).json
            except NuvlaError as e:
                reason = e.reason
                if e.response.status_code == 404:
                    logging.warning(
                        'Retrieve of {} failed. Attempt: {} Will retry in {}s.'.format(job_uri, attempt, wait_time))
                    wait(wait_time)
                else:
                    raise e
        raise NonexistentJobError(reason)

    def is_in_final_state(self):
        return self.get('state') in ('SUCCESS', 'FAILED')

    def set_progress(self, progress):
        if not isinstance(progress, int):
            raise TypeError('progress should be int not {}'.format(type(progress)))

        if not (0 <= progress <= 100):
            raise ValueError('progress shoud be between 0 and 100 not {}'.format(progress))

        self._edit_job('progress', progress)

    def set_status_message(self, status_message):
        self._edit_job('statusMessage', str(status_message))

    def set_return_code(self, return_code):
        if not isinstance(return_code, int):
            raise TypeError('return_code should be int not {}'.format(type(return_code)))

        self._edit_job('returnCode', return_code)

    def set_state(self, state):
        states = ('QUEUED', 'RUNNING', 'FAILED', 'SUCCESS', 'STOPPING', 'STOPPED')
        if state not in states:
            raise ValueError('state should be one of {}'.format(states))

        self._edit_job('state', state)

    def add_affected_resource(self, affected_resource):
        self.add_affected_resources([affected_resource])

    def add_affected_resources(self, affected_resources):
        has_to_update = False
        current_affected_resources_ids = [resource['href'] for resource in self.get('affectedResources', [])]

        for affected_resource in affected_resources:
            if affected_resource not in current_affected_resources_ids:
                current_affected_resources_ids.append(affected_resource)
                has_to_update = True

        if has_to_update:
            self._edit_job('affectedResources', [{'href': id} for id in current_affected_resources_ids])

    def update_job(self, state=None, return_code=None, status_message=None):
        attributes = {}

        if state is not None:
            attributes['state'] = state

        if return_code is not None:
            attributes['returnCode'] = return_code

        if status_message is not None:
            attributes['statusMessage'] = status_message

        if attributes:
            self._edit_job_multi(attributes)

    def consume_when_final_state(self):
        if self.is_in_final_state():
            retry_kazoo_queue_op(self.queue, 'consume')
            logging.info('Great, {} is now in final state; Removed from queue.'.format(self.id))

    def _edit_job(self, attribute_name, attribute_value):
        try:
            response = self.ss_api.cimi_edit(self.id, {attribute_name: attribute_value})
        except (NuvlaError, ConnectionError):
            retry_kazoo_queue_op(self.queue, 'release')
            reason = 'Failed to update attribute "{}" for {}! Put it back in queue.'.format(attribute_name, self.id)
            raise JobUpdateError(reason)
        else:
            self.update(response.json)
            self.consume_when_final_state()

    def _edit_job_multi(self, attributes):
        try:
            response = self.ss_api.cimi_edit(self.id, attributes)
        except (NuvlaError, ConnectionError):
            retry_kazoo_queue_op(self.queue, 'release')
            reason = 'Failed to update following attributes "{}" for {}! '.format(attributes, self.id) \
                     + 'Put it back in queue.'
            raise JobUpdateError(reason)
        else:
            self.update(response.json)
            self.consume_when_final_state()

    def __setitem(self, key, value):
        dict.__setitem__(self, key, value)

    def __setitem__(self, key, value):
        raise TypeError(" '{}' does not support item assignment".format(self.__class__.__name__))

    def __delitem__(self, item):
        raise TypeError(" '{}' does not support item deletion".format(self.__class__.__name__))

    __getattr__ = dict.__getitem__
