# -*- coding: utf-8 -*-

from typing import Optional
from nuvla.api.api import Api as Nuvla


def connector_factory(connector, nuvla_api: Nuvla, credential_id,
                      infrastructure_service: Optional[dict]=None):
    """
    Returns infrastructure connector instance. Connector to be used is derived
    from Nuvla via `credential_id`.

    :param connector: Connector (module) to instantiate with
    :param nuvla_api: nuvla.api.Api, instance
    :param credential_id: str
    :param infrastructure_service: if available, the corresponding infrastructure service
    :return: connector.Connector, instance
    """

    if nuvla_api is None:
        raise ValueError("Nuvla API is not provided!")

    if credential_id is None:
        raise ValueError("Credential id is not provided!")

    credential = nuvla_api.get(credential_id).data

    if not infrastructure_service:
        infrastructure_service_id = credential['parent']

        infrastructure_service = nuvla_api.get(infrastructure_service_id).data

    return connector.instantiate_from_cimi(infrastructure_service, credential)
