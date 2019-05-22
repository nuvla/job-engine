# -*- coding: utf-8 -*-

def load_py_module(module_name):
    namespace = ''
    name = module_name
    if name.find('.') != -1:
        # There's a namespace so we take it into account
        namespace = '.'.join(name.split('.')[:-1])

    return __import__(name, fromlist=namespace)


connector_classes = {
    'swarm': 'nuvla.connector.docker_connector',
    'create_swarm': 'nuvla.connector.docker_machine_connector'
}


def _create_connector_instance(api_infrastructure_service, api_credential):
    if api_infrastructure_service["state"] == "STARTED":
        connector_name = api_infrastructure_service['type']
    else:
        connector_name = "create_swarm"

    connector = load_py_module(connector_classes[connector_name])

    if not hasattr(connector, 'instantiate_from_cimi'):
        raise NotImplementedError('The "{}" is not compatible with the job action'
                                  .format(api_infrastructure_service['type']))
    return connector.instantiate_from_cimi(api_infrastructure_service, api_credential)


def connector_factory(nuvla_api, credential_id):
    """
    Returns infrastructure connector instance. Connector to be used is derived
    from Nuvla via `credential_id`.

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

    return _create_connector_instance(api_infrastructure_service, api_credential)
