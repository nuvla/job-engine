# -*- coding: utf-8 -*-

import glob
import logging
import os

from os.path import dirname, basename, isfile

"""
This package contains code to be executed to process jobs.

Use the @distribution decorator to register a callable as the processor for a specific distribution.

The callable will receive a `controller.Job` object as parameter.
The callable can use the method `job.set_progress` to update the progress of the job.
If the job fail to process, the callable should throw an exception.

Examples:
"""

modules = glob.glob(dirname(__file__) + "/*.py")


class Distributions(object):

    distributions = {}

    @classmethod
    def get_distribution(cls, distribution_name):
        return cls.distributions.get(distribution_name)

    @classmethod
    def register_distribution(cls, distribution_name, distribution):
        # logging.getLogger().setLevel(logging.INFO)
        logging.info('Distribution "{}" registered'.format(distribution_name))
        cls.distributions[distribution_name] = distribution

    @classmethod
    def distribution(cls, distribution_name=None):

        def decorator(f):
            _distribution_name = distribution_name
            if not distribution_name:
                _distribution_name = f.__name__

            if _distribution_name in cls.distributions:
                logging.error('Distribution "{}" is already defined'.format(_distribution_name))
            else:
                cls.register_distribution(_distribution_name, f)

            return f

        return decorator


distribution = Distributions.distribution
get_distribution = Distributions.get_distribution
register_distribution = Distributions.register_distribution
distributions = Distributions.distributions

for f in modules:
    if isfile(f) and not f.endswith('__init__.py'):
        __all__ = [basename(f)[:-3]]
        try:
            from . import *
        except ModuleNotFoundError:
            logging.exception(f'Unable to load module {__all__[0]}')
