#!/usr/bin/env python3.7

import logging
import os
import sys
import time

from nuvla.job.actions.deployment_start import DeploymentStartJob
from nuvla.job.actions.deployment_state import DeploymentStateJob
from nuvla.job.actions.deployment_stop import DeploymentStopJob
from nuvla.job.actions.deployment import DeploymentJob, Deployment
from nuvla.job.job import Job
from nuvla.api.api import Api


log = logging.getLogger('test')


def job_create(nuvla, deployment_id):
    setattr(Job, 'set_progress', lambda x, y: None)
    setattr(Job, '_init', lambda _: None)
    job = Job(nuvla, None)
    job.update({'target-resource': {'href': deployment_id}})
    return job


def all_replicas_running(nuvla_dpl, deployment_id, desired):
    log.info('Checking replicas.')
    node_name = nuvla_dpl.uuid(deployment_id)
    val = nuvla_dpl.get_parameter(deployment_id, node_name,
                                  DeploymentJob.DPARAM_REPLICAS_RUNNING['name'])
    return int(val) == desired


def main():
    nuvla_endpoint = os.environ['NUVLA_ENDPOINT']
    username = os.environ['NUVLA_USERNAME']
    password = os.environ['NUVLA_PASSWORD']

    desired_replicas = 1
    if len(sys.argv) < 2:
        raise SystemExit('Usage: {} <module URI>'.format(sys.argv[0]))
    module = sys.argv[1]

    nuvla = Api(endpoint=nuvla_endpoint, insecure=True)
    nuvla.login_password(username, password)

    nuvla_dpl = Deployment(nuvla)
    deployment = nuvla_dpl.create(module)
    deployment_id = deployment['id']

    job = job_create(nuvla, deployment_id)

    DeploymentStartJob(None, job).do_work()
    time_stop = time.time() + 10
    while not all_replicas_running(nuvla_dpl, deployment_id, desired_replicas) and time.time() < time_stop:
        DeploymentStateJob(None, job).do_work()
        time.sleep(1)
    DeploymentStopJob(None, job).do_work()

    nuvla_dpl.delete(deployment_id)


if __name__ == '__main__':
    main()
