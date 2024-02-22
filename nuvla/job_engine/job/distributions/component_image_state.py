# -*- coding: utf-8 -*-

import time
from ..distribution import DistributionBase
from ..util import override


class ServiceImageStateJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'component_image_state'

    def __init__(self, distributor):
        super(ServiceImageStateJobsDistribution, self).__init__(self.DISTRIBUTION_NAME, distributor)
        self.collect_interval = 3600
        self._start_distribution()

    def user_components(self):
        resp = self.distributor.api.search('module', filter="subtype='component'", select='id,operations')

        components = []
        for r in resp.resources:
            if hasattr(r, 'operations') and 'edit' in r.operations:
                components.append(r.id)
        return components

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
            for component_id in self.user_components():
                job = {'action': self.DISTRIBUTION_NAME,
                       'target-resource': {'href': component_id}}
                if self.job_exists(job):
                    continue
                yield job
            time.sleep(self.collect_interval)
