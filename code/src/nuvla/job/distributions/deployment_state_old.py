# -*- coding: utf-8 -*-

import logging

from ..util import override
from ..distributions import distribution
from .deployment_state import DeploymentStateJobsDistribution


# direct retry on error for long interval jobs
# config sleep time deployment state issue

@distribution('deployment_state_old')
class DeploymentStateOldJobsDistribution(DeploymentStateJobsDistribution):
    DISTRIBUTION_NAME = 'deployment_state_old'
    ACTION_NAME = 'deployment_state_60'

    def __init__(self, distributor):
        super(DeploymentStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60
        self._start_distribution()

    def _get_existing_parents(self, deployments):
        if len(deployments) > 0:
            deployment_parents = [deployment.data.get('parent')
                                  for deployment in deployments
                                  if deployment.data.get('parent')]
            filter_parents = f'id={deployment_parents}'
            parents_resp = self.distributor.api.search(
                'credential', filter=filter_parents, select='id', last=10000)
            return {parent.id for parent in parents_resp.resources}
        else:
            return set()

    def _with_parent(self, deployments, with_parent):
        existing_parents = self._get_existing_parents(deployments)
        for r in deployments:
            p_id = r.data.get('parent')
            if p_id in existing_parents:
                with_parent.append(r)
            else:
                logging.warning(f'Parent {p_id} is missing for {r.id}')

    @override
    def _publish_metric(self, name, value):
        mname = f'job_distribution.deployment_state_old.{name}'
        self.distributor.publish_metric(mname, value)

    @override
    def get_deployments(self):
        filters = f"state='STARTED' and updated<'now-{self.COLLECT_PAST_SEC}s'"
        select = 'id,execution-mode,nuvlabox,parent'
        deployments_resp = self.distributor.api.search('deployment', filter=filters, select=select)
        self._publish_metric('in_started', deployments_resp.count)
        logging.info(f'Deployments in STARTED: {deployments_resp.count}')
        with_parent = []
        self._with_parent(deployments_resp.resources, with_parent)
        self._publish_metric('in_started_with_parent', len(with_parent))
        logging.info(f'Deployments in STARTED with parent: {len(with_parent)}')
        return with_parent
