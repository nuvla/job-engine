#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import requests
from nuvla.job.actions.deployment_state import DeploymentStateJob
from nuvla.api.resources import Deployment
from nuvla.api import Api

deployment_id = os.getenv('NUVLA_DEPLOYMENT_ID')
apikey = os.getenv('NUVLA_API_KEY')
apisecret = os.getenv('NUVLA_API_SECRET')
endpoint = os.getenv('NUVLA_ENDPOINT')


class PushJob(object):
    def __init__(self, api):
        self.api = api


def set_api(nuvla_endpoint):
    tmp_api = Api(endpoint=nuvla_endpoint, insecure=False, reauthenticate=True)
    # check SSL connection
    try:
        tmp_api.get("session")
    except requests.exceptions.SSLError:
        logging.warning("Setting {} with an insecure connection".format(nuvla_endpoint))
        tmp_api = Api(endpoint=nuvla_endpoint, insecure=True, reauthenticate=True)

    return tmp_api


def nuvla_login(api_instance, credential_apikey, credential_apisecret):
    logging.info("Login with API key {}".format(credential_apikey))
    r = api_instance.login_apikey(credential_apikey, credential_apisecret)
    r.raise_for_status()


if __name__ == '__main__':
    logging.info("Starting deployment state job in push mode...")
    if not (deployment_id and apikey and apisecret and endpoint):
        error = "Missing environment variables. Need the deployment ID plus Nuvla endpoint and credentials"
        logging.error(error)
        raise Exception(error)

    api = set_api(endpoint)
    nuvla_login(api, apikey, apisecret)

    # local_app_id = deployment_id.split("/")[-1]
    local_job = PushJob(api)

    logging.info("Initializing DeploymentStateJob class for deployment {}".format(deployment_id))
    ds = DeploymentStateJob(None, local_job)
    nuvla_deployment = ds.api_dpl.get(deployment_id)

    try:
        if Deployment.is_component(nuvla_deployment):
            ds.get_component_state(nuvla_deployment)
        elif Deployment.is_application(nuvla_deployment):
            ds.get_application_state(nuvla_deployment)
        elif Deployment.is_application_kubernetes(nuvla_deployment):
            ds.get_application_kubernetes_state(nuvla_deployment)
    except Exception as ex:
        logging.exception('Failed to get deployment state for {}: {}'.format(deployment_id, ex))
        pass
