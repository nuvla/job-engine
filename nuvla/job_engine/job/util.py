# -*- coding: utf-8 -*-

import os
import sys
import uuid
import time
import random
import logging
import traceback
import warnings

PY2 = sys.version_info[0] == 2
PY3_10 = (3, 10)


def random_wait(secs_min, secs_max):
    time.sleep(random.uniform(secs_min, secs_max))


class InterruptException(Exception):
    pass


def override(func):
    """This is a decorator which can be used to check that a method override a method of the base
    class. If not the case it will result in a warning being emitted."""

    def overrided_func(self, *args, **kwargs):
        bases_functions = []
        for base in self.__class__.__bases__:
            bases_functions += dir(base)

        if func.__name__ not in bases_functions:
            warnings.warn("The method '%s' should override a method of the base class '%s'." %
                          (func.__name__, self.__class__.__bases__[0].__name__),
                          category=SyntaxWarning, stacklevel=2)
        return func(self, *args, **kwargs)

    return overrided_func


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
        logging.warning(
            'retry_kazoo_queue_op: Retrying {} on {}.'.format(function_name, queue.get()))


def status_message_from_exception():
    """
    For the use in the 'except' block.
    """
    ex_type, ex_msg, ex_tb = sys.exc_info()
    if (sys.version_info.major, sys.version_info.minor) >= PY3_10:
        ex = traceback.format_exception(None, ex_msg, ex_tb)
    else:
        ex = traceback.format_exception(etype=ex_type, value=ex_msg, tb=ex_tb)
    return ex_type.__name__ + '-' + ''.join(ex)


def mapv(func, iter1):
    list(map(func, iter1))
