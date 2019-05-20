# -*- coding: utf-8 -*-

from nuvla.connector import docker_connector


def get_credential(api, api_deployment):
    credential_id = api_deployment['credential-id']
    if credential_id is None:
        raise ValueError("Credential id is not set!")

    return api.get(credential_id).data


def get_infrastructure_service(api, api_credential):
    infrastructure_service_id = api_credential['parent']

    return api.get(infrastructure_service_id).data


def create_connector_instance(api_infrastructure_service, api_credential):
    return docker_connector.instantiate_from_cimi(api_infrastructure_service, api_credential)
