#!/usr/bin/env python3.7

import logging
import os
import sys
import time

from nuvla.job_engine.job.actions.deployment_start import DeploymentStartJob
from nuvla.job_engine.job.actions.deployment_state import DeploymentStateJob
from nuvla.job_engine.job.actions.deployment_stop import DeploymentStopJob
from nuvla.api.resources import Deployment, DeploymentParameter, Credential
from nuvla.job_engine.job.job import Job
from nuvla.api.api import Api

log = logging.getLogger('test')


def job_create(nuvla, deployment_id):
    setattr(Job, 'set_progress', lambda x, y: None)
    setattr(Job, '_init', lambda _: None)
    job = Job(nuvla, None)
    job.update({'target-resource': {'href': deployment_id}})
    return job


def all_replicas_running(nuvla_dpl, deployment, desired):
    log.info('Checking replicas.')
    node_name = nuvla_dpl.uuid(deployment)
    val = nuvla_dpl.get_parameter(Deployment.id(deployment), node_name,
                                  DeploymentParameter.REPLICAS_RUNNING['name'])
    return int(val) == desired


def main():
    nuvla_endpoint = os.environ['NUVLA_ENDPOINT']
    username = os.environ['NUVLA_USERNAME']
    password = os.environ['NUVLA_PASSWORD']

    if len(sys.argv) < 3:
        raise SystemExit('Usage: {} <module URI> <infra service URI>'.format(sys.argv[0]))
    module = sys.argv[1]
    infra_service = sys.argv[2]

    desired_replicas = 1

    nuvla = Api(endpoint=nuvla_endpoint, insecure=True, persist_cookie=False)
    nuvla.login_password(username, password)

    nuvla_dpl = Deployment(nuvla)
    deployment = nuvla_dpl.create(module)
    deployment_id = Deployment.id(deployment)

    nuvla_creds = Credential(nuvla)
    creds = nuvla_creds.find(infra_service)
    if len(creds) < 1:
        raise SystemExit('No creds for infra service {}.'.format(infra_service))
    nuvla_dpl.set_infra_cred_id(deployment_id, creds[0].id)

    job = job_create(nuvla, deployment_id)

    DeploymentStartJob(None, job).do_work()

    time_stop = time.time() + 10
    while not all_replicas_running(nuvla_dpl, deployment, desired_replicas) \
            and time.time() < time_stop:
        DeploymentStateJob(None, job).do_work()
        time.sleep(1)

    DeploymentStopJob(None, job).do_work()

    nuvla_dpl.delete(deployment_id)


if __name__ == '__main__':
    main()
