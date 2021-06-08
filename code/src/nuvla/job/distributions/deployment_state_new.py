# -*- coding: utf-8 -*-

import logging

from nuvla.job.util import override
from ..distributions import distribution
from .deployment_state import DeploymentStateJobsDistribution


@distribution('deployment_state_new')
class DeploymentStateNewJobsDistribution(DeploymentStateJobsDistribution):
    DISTRIBUTION_NAME = 'deployment_state_new'

    def __init__(self, distributor):
        super(DeploymentStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 10
        self._start_distribution()

    @override
    def _publish_metric(self, name, value):
        mname = f'job_distribution.deployment_state_new.{name}'
        self.distributor.publish_metric(mname, value)

    @override
    def get_deployments(self):
        filters = f"state='STARTED' and updated>='now-{self.COLLECT_PAST_SEC}s'"
        select = 'id,execution-mode,nuvlabox'
        logging.info(f'Filter: {filters}. Select: {select}')
        active = self.distributor.api.search('deployment', filter=filters, select=select)
        self._publish_metric('in_started', active.count)
        logging.info(f'Deployments in STARTED: {active.count}')
        return active.resources
