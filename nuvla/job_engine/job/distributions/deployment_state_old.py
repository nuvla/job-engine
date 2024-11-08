# -*- coding: utf-8 -*-

import logging

from ..util import override, version_smaller
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

    def filter_deployments_without_parents(self, deployments):
        existing_parents = self._get_existing_parents(deployments)
        deployments_filtered = []
        for deployment in deployments:
            p_id = deployment.data.get('parent')
            if p_id in existing_parents:
                deployments_filtered.append(deployment)
            else:
                logging.warning(f'Parent {p_id} is missing for {deployment.id}')
        return deployments_filtered

    def _get_ne_not_supporting_coe_resources(self, deployments: list):
        ne_ids = [d['nuvlabox'] for d in deployments if d.get('nuvlabox')]
        if len(ne_ids) > 0:
            filter_edges = f'id={ne_ids} and nuvlabox-engine-version!=null'
            resp = self.distributor.api.search(
                'credential', filter=filter_edges, select='id, nuvlabox-engine-version', last=10000)
            return {ne.id for ne in resp.resources if version_smaller(ne.get('nuvlabox-engine-version'), (2, 16, 2))}
        else:
            return set()

    def filter_deployments_ne_support_coe_resources(self, deployments: list):
        ne_ids = self._get_ne_not_supporting_coe_resources(deployments)
        return [d for d in deployments if d.get('nuvlabox') is None or d.get('nuvlabox') in ne_ids]

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
        deployments_with_parents = self.filter_deployments_without_parents(deployments_resp.resources)
        self._publish_metric('in_started_with_parent', len(deployments_with_parents))
        logging.info(f'Deployments in STARTED with parent: {len(deployments_with_parents)}')
        deployments = self.filter_deployments_ne_support_coe_resources(deployments_with_parents)
        logging.info(f'Deployments in STARTED with parent and not supporting coe resources: {len(deployments)}')
        return deployments
