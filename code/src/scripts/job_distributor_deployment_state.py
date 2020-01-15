#!/usr/bin/env python
# -*- coding: utf-8 -*-

from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override


class DeploymentStateJobsDistributor(Distributor):
    ACTION_NAME = 'deployment_state'

    def __init__(self):
        self.collect_interval = 10
        super(Distributor, self).__init__()
        self.collect_interval = self.args.interval

    def _set_command_specific_options(self, parser):
        hmsg = 'Jobs distribution interval in seconds (default: {})'\
            .format(self.collect_interval)
        parser.add_argument('--interval', dest='interval', metavar='INTERVAL',
                            default=self.collect_interval, type=int, help=hmsg)

    def active_deployments(self):
        return map(lambda x: x.id,
                   self.api.search('deployment',
                                   filter="state='STARTED'", select='id').resources)

    def job_exists(self, job):
        filters = "(state='QUEUED' or state='RUNNING')" \
                  " and action='{0}'" \
                  " and target-resource/href='{1}'"\
            .format(job['action'], job['target-resource']['href'])
        jobs = self.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        for deployment_id in self.active_deployments():
            job = {'action': self._get_jobs_type(),
                   'target-resource': {'href': deployment_id}}
            if self.job_exists(job):
                continue
            yield job

    @override
    def _get_jobs_type(self):
        return self.ACTION_NAME


if __name__ == '__main__':
    main(DeploymentStateJobsDistributor)
