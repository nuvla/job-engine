# -*- coding: utf-8 -*-

import logging

from nuvla.api import NuvlaError
from nuvla.job.util import override
from .DistributionBase import DistributionBase

COLLECT_INTERVAL_SHORT = 10
COLLECT_PAST_SEC = 120


class DeploymentStateJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'deployment_state'

    def __init__(self, distributor):
        super(DeploymentStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = COLLECT_INTERVAL_SHORT
        self._start_distribution()

    def _with_parent(self, active, with_parent):
        for r in active.resources:
            p_id = r.data['parent']
            try:
                self.distributor.api.get(p_id, select='')
                with_parent.append(r)
            except NuvlaError:
                logging.warning(f'Parent {p_id} is missing for {r.id}')

    def _old_deployments(self):
        return self.collect_interval > COLLECT_INTERVAL_SHORT

    def _publish_metric(self, name, value):
        interval = 'old' if self._old_deployments() else 'new'
        mname = f'job_distributor.{self.DISTRIBUTION_NAME}.{interval}.{name}'
        self.distributor.publish_metric(mname, value)

    def active_deployments(self):
        # Collect old or new deployments.
        if self._old_deployments():
            filters = f"state='STARTED' and updated<'now-{COLLECT_PAST_SEC}s'"
            select = 'id,execution-mode,nuvlabox,parent'
        else:
            filters = f"state='STARTED' and updated>='now-{COLLECT_PAST_SEC}s'"
            select = 'id,execution-mode,nuvlabox'
        logging.info(f'Filter: {filters}. Select: {select}')
        active = self.distributor.api.search('deployment', filter=filters, select=select)
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
        jobs = self.distributor.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        skipped = 0
        for deployment in self.active_deployments():
            job = {'action': self.DISTRIBUTION_NAME,
                   'target-resource': {'href': deployment.id}}

            nuvlabox = deployment.data.get('nuvlabox')
            if nuvlabox:
                job['acl'] = {'edit-data': [nuvlabox],
                              'manage': [nuvlabox],
                              'owners': ['group/nuvla-admin']}

            exec_mode = deployment.data.get('execution-mode')
            if exec_mode in ['mixed', 'pull']:
                job['execution-mode'] = 'pull'
            else:
                job['execution-mode'] = 'push'

            if self.job_exists(job):
                skipped += 1
                continue
            yield job
        self._publish_metric('skipped_exist', skipped)
        logging.info(f'Deployments skipped (jobs already exist): {skipped}')
