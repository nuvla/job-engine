# -*- coding: utf-8 -*-

import logging

from nuvla.api import NuvlaError
from ..util import override
from ..distributions import distribution
from .deployment_state import DeploymentStateJobsDistribution


### direct retry on error for long interval jobs
### config sleep time deployment state issue


@distribution('deployment_state_old')
class DeploymentStateOldJobsDistribution(DeploymentStateJobsDistribution):
    DISTRIBUTION_NAME = 'deployment_state_old'
    ACTION_NAME = 'deployment_state_60'

    def __init__(self, distributor):
        super(DeploymentStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60
        self._start_distribution()

    def _with_parent(self, active, with_parent):
        for r in active.resources:
            p_id = r.data['parent']
            try:
                self.distributor.api.get(p_id, select='')
                with_parent.append(r)
            except NuvlaError:
                logging.warning(f'Parent {p_id} is missing for {r.id}')

    @override
    def _publish_metric(self, name, value):
        mname = f'job_distribution.deployment_state_old.{name}'
        self.distributor.publish_metric(mname, value)

    @override
    def get_deployments(self):
        filters = f"state='STARTED' and updated<'now-{self.COLLECT_PAST_SEC}s'"
        select = 'id,execution-mode,nuvlabox,parent'
        logging.info(f'Filter: {filters}. Select: {select}')
        active = self.distributor.api.search('deployment', filter=filters, select=select)
        self._publish_metric('in_started', active.count)
        logging.info(f'Deployments in STARTED: {active.count}')
        with_parent = []
        self._with_parent(active, with_parent)
        self._publish_metric('in_started_with_parent', len(with_parent))
        logging.info(f'Deployments in STARTED with parent: {len(with_parent)}')
        return with_parent
