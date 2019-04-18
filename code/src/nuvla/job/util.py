# -*- coding: utf-8 -*-

import os
import sys
import uuid
import random
import warnings
import logging
import threading

PY2 = sys.version_info[0] == 2


def wait(secs):
    e = threading.Event()
    e.wait(timeout=secs)


def random_wait(secs_min, secs_max):
    wait(random.uniform(secs_min, secs_max))


class InterruptException(Exception):
    pass


def override(func):
    """This is a decorator which can be used to check that a method override a method of the base class.
    If not the case it will result in a warning being emitted."""

    def overrided_func(self, *args, **kwargs):
        bases_functions = []
        for base in self.__class__.__bases__:
            bases_functions += dir(base)

        if func.__name__ not in bases_functions:
            warnings.warn("The method '%s' should override a method of the base class '%s'." %
                          (func.__name__, self.__class__.__bases__[0].__name__), category=SyntaxWarning, stacklevel=2)
        return func(self, *args, **kwargs)

    return overrided_func


def load_py_module(module_name):
    namespace = ''
    name = module_name
    if name.find('.') != -1:
        # There's a namespace so we take it into account
        namespace = '.'.join(name.split('.')[:-1])

    return __import__(name, fromlist=namespace)


def from_data_uuid(text):
    class NullNameSpace:
        bytes = b''

    return str(uuid.uuid3(NullNameSpace, text))


def assure_path_exists(path):
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
        os.makedirs(dir)


def retry_kazoo_queue_op(queue, function_name):
    while not getattr(queue, function_name)():
        random_wait(0.1, 5)
        logging.warn('Retrying {} on {}.'.format(function_name, queue.get()))


connector_classes = {
    'swarm': 'nuvla.connector.docker_connector',
    'create_swarm': 'nuvla.connector.docker_machine_connector'
}


def create_connector_instance(api_infrastructure_service, api_credential):
    if api_infrastructure_service["state"] == "STARTED":
        connector_name = api_infrastructure_service['type']
    else:
        connector_name = "create_swarm"

    connector = load_py_module(connector_classes[connector_name])

    if not hasattr(connector, 'instantiate_from_cimi'):
        raise NotImplementedError('The "{}" is not compatible with the job action'
                                  .format(api_infrastructure_service['type']))
    return connector.instantiate_from_cimi(api_infrastructure_service, api_credential)
