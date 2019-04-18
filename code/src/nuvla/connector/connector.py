# -*- coding: utf-8 -*-

from abc import abstractmethod, abstractproperty
from functools import wraps


def should_connect(f):
    @wraps(f)
    def wrapper(self, *f_args, **f_kwargs):
        connect_result = None
        try:
            connect_result = self.connect()
            result = f(self, *f_args, **f_kwargs)
        except Exception as e:
            raise e
        finally:
            self.clear_connection(connect_result)
        return result

    return wrapper


class ConnectorError(Exception):
    def __init__(self, reason):
        super(ConnectorError, self).__init__(reason)
        self.reason = reason


class Connector(object):

    def __init__(self, **kwargs):
        self.kwargs = kwargs

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
    def start(self, **kwargs):
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
