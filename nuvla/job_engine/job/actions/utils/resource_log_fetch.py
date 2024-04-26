# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from nuvla.api.util.date import parse_nuvla_date

def get_last_line_timestamp(lines: Optional[List[str]]) -> Optional[str]:
    return lines[-1].strip().split(' ')[0] if lines else None


def reduce_timestamp_precision(timestamp: Optional[str]) -> Optional[str]:
    # timestamp limit precision to be compatible with server to pico
    return timestamp[:23] + 'Z' if timestamp else None


def last_timestamp_of_logs(log: dict) -> Optional[str]:
    log_lines = filter(None, log.values())
    last_lines = list(map(get_last_line_timestamp, log_lines))
    return max(last_lines) if last_lines else None


def build_update_resource_log(log: dict) -> dict:
    update_body = {'log': log}
    new_last_timestamp = last_timestamp_of_logs(log)
    if new_last_timestamp:
        update_body['last-timestamp'] = \
            reduce_timestamp_precision(new_last_timestamp)
    return update_body


class ResourceLogFetchJob(ABC):

    def __init__(self, _, job):
        self._log = None
        self._connector = None
        self.job = job
        self.api = job.api
        self.resource_log_id = self.job['target-resource']['href']
        self.resource_log = self.get_resource_log(self.resource_log_id)
        self.resource_log_parent = self.resource_log['parent']

    @property
    @abstractmethod
    def log(self):
        pass

    @property
    @abstractmethod
    def connector(self):
        pass

    def all_components(self):
        return []

    def get_component_logs(self, component: str, since: datetime,
                           lines: int) -> str:

        self.log.debug(f"Calling get_component_logs...\n\
            Connector is set to: {self.connector.__class__.__name__}")

        return self.connector.log(component, since, lines)

    def get_resource_log(self, log_id: str) -> dict:
        return self.api.get(log_id).data

    def update_resource_log(self, log_id: str, resource_log: dict) -> None:
        self.api.edit(log_id, resource_log)

    def get_list_components(self) -> List[str]:
        cs = self.resource_log['components']
        return cs if cs else self.all_components()

    def get_components_logs(self) -> dict:
        since = self.get_since()
        components = self.get_list_components()
        self.log.debug(f"components {components}")
        lines = self.resource_log.get('lines', 200)
        log = {}
        for component in components:
            try:
                self.log.debug(f"component {component} since {since} and lines {lines}")
                component_logs = self.get_component_logs(
                    component, since, lines).strip().splitlines()
            except Exception as e:
                self.log.error(f'Cannot fetch {component} log: {str(e)}')
                component_logs = []
            log[component] = component_logs
        return log

    def get_since(self) -> datetime:
        last_timestamp = self.resource_log.get('last-timestamp')
        t = last_timestamp or self.resource_log.get('since')
        return parse_nuvla_date(t) if t else datetime.utcfromtimestamp(0)

    def fetch_log(self):
        self.update_resource_log(
            self.resource_log_id, build_update_resource_log(
                self.get_components_logs()))

    def fetch_resource_log(self):
        self.log.info(f'Job started for {self.resource_log_id}')
        self.job.set_progress(10)
        try:
            self.fetch_log()
        except Exception as e1:
            self.log.error(
                f'Failed to {self.job["action"]} {self.resource_log_id}: {e1}')
            try:
                self.job.set_status_message(repr(e1))
            except Exception as e2:
                self.log.error(
                    f'Failed to set error state for {self.resource_log_id}: {e2}')
            raise e1
        return 0

    def do_work(self):
        return self.fetch_resource_log()
