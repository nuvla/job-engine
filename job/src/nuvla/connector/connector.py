# -*- coding: utf-8 -*-

from __future__ import print_function
from abc import abstractmethod, abstractproperty
from functools import wraps


def should_connect(f):
    @wraps(f)
    def wrapper(self, *f_args, **f_kwargs):
        connect_result = self.connect()
        result = f(self, *f_args, **f_kwargs)
        self.clear_connection(connect_result)
        return result

    return wrapper


class Connector(object):

    def __init__(self, api_infrastructure_service, api_credential, api_endpoint=None):
        self.api_connector = api_infrastructure_service
        self.api_credential = api_credential
        self.api_endpoint = api_endpoint

    @abstractproperty
    def connector_type(self):
        pass

    @abstractmethod
    def connect(self):
        pass

    def clear_connection(self, connect_result):
        pass

    @abstractmethod
    @should_connect
    def start(self, api_deployment):
        pass

    @abstractmethod
    @should_connect
    def stop(self, ids):
        pass

    @abstractmethod
    def list(self):
        pass

    @abstractmethod
    def extract_vm_id(self, vm):
        pass

    @abstractmethod
    def extract_vm_ip(self, vm):
        pass

    @abstractmethod
    def extract_vm_ports_mapping(self, vm):
        pass

    @abstractmethod
    def extract_vm_state(self, vm):
        pass
