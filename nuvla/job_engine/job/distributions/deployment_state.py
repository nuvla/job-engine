# -*- coding: utf-8 -*-

import logging
from abc import abstractmethod
from nuvla.api.util.filter import filter_and

from ..job import JOB_QUEUED, JOB_RUNNING
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
    def get_deployments(self):
        return []

    def _get_exiting_jobs(self, deployments):
        filter_states = f'state={[JOB_QUEUED, JOB_RUNNING]}'
        filter_action = f'action="{self.ACTION_NAME}"'
        deployment_ids = [deployment.id for deployment in deployments]
        filter_targets = f'target-resource/href={deployment_ids}'
        filter_jobs = filter_and([filter_states, filter_action, filter_targets])
        jobs = self.distributor.api.search(
            'job', filter=filter_jobs, select='target-resource', last=10000)
        return {job.data.get('target-resource', {}).get('href')
                for job in jobs.resources}

    def _build_job(self, deployment):
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
        return job

    @override
    def job_generator(self):
        skipped = 0
        deployments = self.get_deployments()
        if len(deployments) > 0:
            existing_jobs = self._get_exiting_jobs(deployments)
            for deployment in deployments:
                if deployment.id in existing_jobs:
                    skipped += 1
                else:
                    yield self._build_job(deployment)
            self._publish_metric('skipped_exist', skipped)
            logging.info(f'Deployments skipped (jobs already exist): {skipped}')
