# -*- coding: utf-8 -*-

import logging
from abc import abstractmethod

from nuvla.api.models import CimiResource

from ..util import override
from ..distribution import DistributionBase


class DeploymentStateJobsDistribution(DistributionBase):
    DISTRIBUTION_NAME = 'deployment_state'
    COLLECT_PAST_SEC = 120
    ACTION_NAME = 'deployment_state'

    @abstractmethod
    def _publish_metric(self, name, value):
        pass

    @abstractmethod
    def get_deployments(self) -> list[CimiResource]:
        return []

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
        for deployment in self.get_deployments():
            job = {'action': self.ACTION_NAME,
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
