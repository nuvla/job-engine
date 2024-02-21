# -*- coding: utf-8 -*-

import time
from ..util import override
from ..distributions import distribution
from ..distribution import DistributionBase


@distribution('service_image_state')
class ServiceImageStateJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'service_image_state'

    def __init__(self, distributor):
        super(ServiceImageStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 3600
        self._start_distribution()

    def active_deployments(self):
        return map(lambda x: x.id,
                   self.distributor.api.search('deployment',
                                               filter="state='STARTED' and module/subtype='component'",
                                               select='id').resources)

    def job_exists(self, job):
        filters = "(state='QUEUED' or state='RUNNING')" \
                  " and action='{0}'" \
                  " and target-resource/href='{1}'" \
            .format(job['action'], job['target-resource']['href'])
        jobs = self.distributor.api.search('job', filter=filters, last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        while True:
            for deployment_id in self.active_deployments():
                job = {'action': self.DISTRIBUTION_NAME,
                       'target-resource': {'href': deployment_id}}
                if self.job_exists(job):
                    continue
                yield job
            time.sleep(self.collect_interval)
