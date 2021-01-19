#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from nuvla.api import NuvlaError

from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override

COLLECT_INTERVAL_SHORT = 10
COLLECT_PAST_SEC = 120


class DeploymentStateJobsDistributor(Distributor):
    ACTION_NAME = 'deployment_state'

    def __init__(self):
        self.collect_interval = COLLECT_INTERVAL_SHORT
        super(Distributor, self).__init__()
        self.collect_interval = self.args.interval

    def _set_command_specific_options(self, parser):
        hmsg = 'Jobs distribution interval in seconds (default: {})'\
            .format(self.collect_interval)
        parser.add_argument('--interval', dest='interval', metavar='INTERVAL',
                            default=self.collect_interval, type=int, help=hmsg)

    def _with_parent(self, active, with_parent):
        for r in active.resources:
            p_id = r.data['parent']
            try:
                self.api.get(p_id, select='')
                with_parent.append(r)
            except NuvlaError as ex:
                logging.warning(f'Parent {p_id} is missing for {r.id}')

    def _old_deployments(self):
        return self.collect_interval > COLLECT_INTERVAL_SHORT

    def _publish_metric(self, name, value):
        interval = 'old' if self._old_deployments() else 'new'
        mname = f'job_distributor.{self.ACTION_NAME}.{interval}.{name}'
        super()._publish_metric(mname, value)

    def active_deployments(self):
        # Collect old or new deployments.
        if self._old_deployments():
            filters = f"state='STARTED' and updated<'now-{COLLECT_PAST_SEC}s'"
            select = 'id,parent'
        else:
            filters = f"state='STARTED' and updated>='now-{COLLECT_PAST_SEC}s'"
            select = 'id'
        logging.info(f'Filter: {filters}. Select: {select}')
        active = self.api.search('deployment', filter=filters, select=select)
        self._publish_metric('in_started', active.count)
        logging.info(f'Deployments in STARTED: {active.count}')

        # Check parents of long running deployments still exist.
        if self._old_deployments():
            with_parent = []
            self._with_parent(active, with_parent)
            self._publish_metric('in_started_with_parent', len(with_parent))
            logging.info(f'Deployments in STARTED with parent: {len(with_parent)}')
            return with_parent
        else:
            return active.resources

    def job_exists(self, job):
        filters = "(state='QUEUED' or state='RUNNING')" \
                  " and action='{0}'" \
                  " and target-resource/href='{1}'"\
            .format(job['action'], job['target-resource']['href'])
        jobs = self.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        skipped = 0
        for deployment in self.active_deployments():
            job = {'action': self._get_jobs_type(),
                   'target-resource': {'href': deployment.id}}

            if deployment.get('execution-mode'):
                job['execution-mode'] = deployment['execution-mode']

            if self.job_exists(job):
                skipped += 1
                continue
            yield job
        self._publish_metric('skipped_exist', skipped)
        logging.info(f'Deployments skipped (jobs already exist): {skipped}')

    @override
    def _get_jobs_type(self):
        return f'{self.ACTION_NAME}_{self.collect_interval}'


if __name__ == '__main__':
    main(DeploymentStateJobsDistributor)
