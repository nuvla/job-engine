# -*- coding: utf-8 -*-

import glob
import logging
import os

from os.path import dirname, basename, isfile

"""
This package contains code to be executed to process jobs.

Use the @action decorator to register a callable as the processor for a specific action.

The callable will receive a `controller.Job` object as parameter.
The callable can use the method `job.set_progress` to update the progress of the job.
If the job fail to process, the callable should throw an exception.

Examples:
"""

modules = glob.glob(dirname(__file__) + "/*.py")


class Actions(object):

    actions = {}

    @classmethod
    def get_action(cls, action_name):
        return cls.actions.get(action_name)

    @classmethod
    def register_action(cls, action_name, action):
        # logging.getLogger().setLevel(logging.INFO)
        logging.info('Action "{}" registered'.format(action_name))
        cls.actions[action_name] = action

    @classmethod
    def action(cls, action_name=None, pull_mode_support=False):

        def decorator(f):
            _action_name = action_name
            if not action_name:
                _action_name = f.__name__

            if _action_name in cls.actions:
                logging.error('Action "{}" is already defined'.format(_action_name))
            else:
                if os.getenv('IMAGE_NAME', '') == 'job-lite':
                    if pull_mode_support:
                        cls.register_action(_action_name, f)
                else:
                    cls.register_action(_action_name, f)

            return f

        return decorator


class ActionNotImplemented(Exception):
    pass


action = Actions.action
get_action = Actions.get_action
register_action = Actions.register_action

for f in modules:
    if isfile(f) and not f.endswith('__init__.py'):
        __all__ = [basename(f)[:-3]]
        try:
            from . import *
        except ModuleNotFoundError:
            logging.exception(f'Unable to load module {__all__[0]}')
