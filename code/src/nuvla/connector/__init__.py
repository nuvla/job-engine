# -*- coding: utf-8 -*-


def connector_factory(connector_class, nuvla_api, credential_id):
    """
    Returns infrastructure connector instance. Connector to be used is derived
    from Nuvla via `credential_id`.

    :param connector_class: Connector class to instanciate with
    :param nuvla_api: nuvla.api.Api, instance
    :param credential_id: str
    :return: connector.Connector, instance
    """

    if nuvla_api is None:
        raise ValueError("Nuvla API is not provided!")

    if credential_id is None:
        raise ValueError("Credential id is not provided!")

    api_credential = nuvla_api.get(credential_id).data

    infrastructure_service_id = api_credential['parent']

    api_infrastructure_service = nuvla_api.get(infrastructure_service_id).data

    return connector_class.instantiate_from_cimi(api_infrastructure_service, api_credential)
