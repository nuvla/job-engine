# -*- coding: utf-8 -*-

import logging

from nuvla.api.util.filter import filter_and
from ..job import JOB_RUNNING, JOB_QUEUED
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase
from .register_usage_record import RegisterUsageRecordJobsDistribution


@distribution('register_usage_record_new_deployment')
class RegisterUsageRecordNewDeploymentJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'register_usage_record_updated_deployment'

    def __init__(self, distributor):
        super(RegisterUsageRecordNewDeploymentJobsDistribution, self).__init__(
            self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 60
        self._start_distribution()

    def job_exists(self, job):
        jobs = self.distributor.api.search(
            'job',
            filter=filter_and(
                [f'state={[JOB_QUEUED, JOB_RUNNING]}'
                 f"action='{job['action']}'",
                 f"target-resource/href='{job['target-resource']['href']}'"]),
            last=0)
        return jobs.count > 0

    def new_deployments(self):
        try:
            return self.distributor.api.search(
                'deployment',
                filter=filter_and(["module/price!=null",
                                   "state='STARTED'",
                                   "created>'now-5m'"]),
                select='id, owner, module',
                last=10000).resources
        except Exception as ex:
            logging.error(f'Failed to search for deployment: {ex}')
            return []

    @staticmethod
    def unique_owners(deployments):
        owners = []
        for deployment in deployments:
            owner = deployment.data.get('owner')
            module_acl = deployment.data.get('module', {}).get('acl', {})
            module_owners = module_acl.get('owners', [])
            module_editors = module_acl.get('edit-data', [])
            owners = owners + [owner] if \
                owner not in owners and \
                owner not in module_owners and \
                owner not in module_editors \
                else owners
        return owners

    def resolve_customer(self, owner):
        customers = self.distributor.api.search(
            'customer',
            filter=f"parent='{owner}'",
            select='id').resources
        return customers[0].id if len(customers) == 1 else None

    def owner_resource_id(self, owner):
        customer = self.resolve_customer(owner)
        return customer if customer else owner

    @override
    def job_generator(self):
        deployments = self.new_deployments()
        logging.info(f'New deployments count: {len(deployments)}')
        owners = self.unique_owners(deployments)
        logging.info(f'New deployments owners count: {len(owners)}')
        for owner in owners:
            job = {'action': RegisterUsageRecordJobsDistribution.DISTRIBUTION_NAME,
                   'target-resource': {'href': self.owner_resource_id(owner)}}
            if self.job_exists(job):
                continue
            yield job
