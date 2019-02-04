# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import sys
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


def load_module(module_name):
    namespace = ''
    name = module_name
    if name.find('.') != -1:
        # There's a namespace so we take it into account
        namespace = '.'.join(name.split('.')[:-1])

    return __import__(name, fromlist=namespace)


def assure_path_exists(path):
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
        os.makedirs(dir)


def retry_kazoo_queue_op(queue, function_name):
    while not getattr(queue, function_name)():
        random_wait(0.1, 5)
        logging.warn('Retrying {} on {}.'.format(function_name, queue.get()))


connector_classes = {
    'azure': 'slipstream_azure.AzureClientCloud',
    'cloudstack': 'slipstream_cloudstack.CloudStackClientCloud',
    'cloudstackadvancedzone': 'slipstream_cloudstack.CloudStackAdvancedZoneClientCloud',
    'ec2': 'slipstream_ec2.Ec2ClientCloud',
    'exoscale': 'slipstream_exoscale.ExoscaleClientCloud',
    'nuvlabox': 'slipstream_nuvlabox.NuvlaBoxClientCloud',
    'opennebula': 'slipstream_opennebula.OpenNebulaClientCloud',
    'openstack': 'slipstream_openstack.OpenStackClientCloud',
    'otc': 'slipstream_otc.OpenTelekomClientCloud',
    'softlayer': 'slipstream_nativesoftlayer.NativeSoftLayerClientCloud',
    'docker': 'slipstream_docker.DockerClientCloud'
}
