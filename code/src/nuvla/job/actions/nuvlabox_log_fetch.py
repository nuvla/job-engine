# -*- coding: utf-8 -*-

import logging

from datetime import datetime
from ...connector import nuvlabox_connector as NB
from ..actions import action

action_name = 'fetch_nuvlabox_log'

log = logging.getLogger(action_name)


@action(action_name, True)
class NuvlaBoxLogFetchJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def fetch_log(self, nuvlabox_log):
        connector = NB.NuvlaBoxConnector(api=self.api, nuvlabox_id=nuvlabox_log['parent'], job=self.job)

        max_lines = 1000
        result, new_last_timestamp = connector.log(nuvlabox_log)[:max_lines]

        update_log = {
            'log': result,
            'last-timestamp': new_last_timestamp if new_last_timestamp else f'{datetime.utcnow().isoformat()[:23]}Z'
        }

        self.api.edit(nuvlabox_log['id'], update_log)

    def fetch_nuvlabox_log(self):
        nuvlabox_log_id = self.job['target-resource']['href']

        log.info('Job started for fetching NuvlaBox logs at {}.'.format(nuvlabox_log_id))
        nuvlabox_log = self.api.get(
            nuvlabox_log_id, select='id, parent, since, lines, last-timestamp').data

        self.job.set_progress(10)

        try:
            self.fetch_log(nuvlabox_log)
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], nuvlabox_log_id, ex))
            try:
                self.job.set_status_message(repr(ex))
            except Exception as ex_state:
                log.error('Failed to set error state for {0}: {1}'
                          .format(nuvlabox_log_id, ex_state))

            raise ex

        return 0

    def do_work(self):
        return self.fetch_nuvlabox_log()
