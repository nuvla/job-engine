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

    def fetch_log(self, resource_log):
        connector = NB.NuvlaBoxConnector(api=self.api,
                                         nuvlabox_id=resource_log['parent'],
                                         job=self.job)

        result, new_last_timestamp = connector.log(resource_log)

        last_timestamp = new_last_timestamp if new_last_timestamp \
            else f'{datetime.utcnow().isoformat()[:23]}Z'

        self.api.edit(resource_log['id'], {'log': result,
                                           'last-timestamp': last_timestamp})

    def fetch_nuvlabox_log(self):
        log_id = self.job['target-resource']['href']

        log.info(f'Job started for fetching NuvlaBox logs at {log_id}.')
        resource_log = self.api.get(
            log_id, select='id, parent, since, lines, last-timestamp').data

        self.job.set_progress(10)

        try:
            self.fetch_log(resource_log)
        except Exception as ex:
            log.error(f"Failed to {self.job['action']} {log_id}: {ex}")
            try:
                self.job.set_status_message(repr(ex))
            except Exception as ex_state:
                log.error(f'Failed to set error state for {log_id}: {ex_state}')

            raise ex

        return 0

    def do_work(self):
        return self.fetch_nuvlabox_log()
