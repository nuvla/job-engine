#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from nuvla.job.base import main
from nuvla.job.distributor import Distributor
from nuvla.job.util import override

from nuvla.job.actions.nuvla import Module


class ServiceImageStateJobsDistributor(Distributor):
    ACTION_NAME = 'component_image_state'

    def __init__(self):
        self.collect_interval = 3600
        super(Distributor, self).__init__()
        self.collect_interval = self.args.interval

    def _set_command_specific_options(self, parser):
        hmsg = 'Jobs distribution interval in seconds (default: {})'\
            .format(self.collect_interval)
        parser.add_argument('--interval', dest='interval', metavar='INTERVAL',
                            default=self.collect_interval, type=int, help=hmsg)

    def user_components(self):
        module = Module(self.api)
        resp = module.find(filter="subtype='component'", select='id,operations')
        components = []
        for r in resp.resources:
            if hasattr(r, 'operations'):
                for op in r.operations:
                    if op.get('rel', '') == 'edit':
                        components.append(r.id)
        return components

    def job_exists(self, job):
        filters = "(state='QUEUED' or state='RUNNING')" \
                  " and action='{0}'" \
                  " and target-resource/href='{1}'"\
            .format(job['action'], job['target-resource']['href'])
        jobs = self.api.search('job', filter=filters, select='', last=0)
        return jobs.count > 0

    @override
    def job_generator(self):
        while True:
            for component_id in self.user_components():
                job = {'action': self._get_jobs_type(),
                       'target-resource': {'href': component_id}}
                if self.job_exists(job):
                    continue
                yield job
            time.sleep(self.collect_interval)

    @override
    def _get_jobs_type(self):
        return self.ACTION_NAME


if __name__ == '__main__':
    main(ServiceImageStateJobsDistributor)
