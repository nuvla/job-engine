# -*- coding: utf-8 -*-
import os
import re
import json
import base64
import hashlib
import logging
import signal
from contextlib import contextmanager
from datetime import datetime, timedelta
from subprocess import run, STDOUT, PIPE, TimeoutExpired, CompletedProcess
from tempfile import NamedTemporaryFile

log = logging.getLogger('connector_utils')

LOCAL = 'local'


def is_endpoint_local(endpoint):
    is_local = isinstance(endpoint, str) and (endpoint.startswith('unix://') or endpoint == LOCAL)
    return not endpoint or is_local


def _time_rm_nanos(time_str):
    time1, time2 = time_str.rsplit('.', 1)
    return '.'.join([time1, time2[:6]])


def timestr2dtime(time_str):
    return datetime.fromisoformat(_time_rm_nanos(time_str))


def timenow():
    return datetime.utcnow()


def timenow_plus(seconds):
    return timenow() + timedelta(seconds=seconds)


def utc_from_now_iso(seconds):
    return timenow_plus(seconds).isoformat('T', timespec='milliseconds') + 'Z'


def unique_id(*args):
    return hashlib.sha256(':'.join(map(str, args)).encode()).hexdigest()


def append_os_env(env):
    final_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if value:
                final_env[key] = value
    return final_env


def execute_cmd(cmd, **kwargs) -> CompletedProcess:
    if kwargs.get('env'):
        opt_env = append_os_env(kwargs.get('env'))
    else:
        opt_env = None
    opt_input = kwargs.get('input')
    timeout = kwargs.get('timeout', 120)
    stderr = STDOUT if kwargs.get('sterr_in_stdout', False) else PIPE
    log.debug('Run command (timeout: %s): %s \n'
              'with environment: %s \n'
              'with input: %s',
              timeout, cmd, opt_env, opt_input)
    try:
        result = run(cmd, stdout=PIPE, stderr=stderr, env=opt_env, input=opt_input,
                     timeout=timeout, encoding='UTF-8')
        log.debug('Command result: %s', result)
    except TimeoutExpired:
        message = f'Command execution timed out after {timeout} seconds'
        log.exception(message)
        raise Exception(message)
    if result.returncode == 0:
        return result
    else:
        log.exception(result)
        raise Exception(result.stderr)


def join_stderr_stdout(process_result: CompletedProcess):
    return f'StdOut: \n{process_result.stdout} \n\nStdErr: \n{process_result.stderr}'


def create_tmp_file(content):
    file = NamedTemporaryFile(delete=True)
    file.write(content.encode())
    file.flush()
    return file


def generate_registry_config(registries_auth: list):
    auths = {}
    for registry_auth in registries_auth:
        user_pass = registry_auth['username'] + ':' + registry_auth['password']
        auth = base64.b64encode(user_pass.encode('ascii')).decode('utf-8')
        auths['https://' + registry_auth['serveraddress']] = {'auth': auth}
    return json.dumps({'auths': auths})


@contextmanager
def timeout(deadline):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(deadline)
    try:
        yield
    except TimeoutError:
        raise
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def remove_protocol_from_url(endpoint: str):
    return endpoint.split('://')[1] if '://' in endpoint else endpoint


def extract_host_from_url(url: str):
    return re.search('(?:http.*://)?(?P<host>[^:/ ]+)', url).group('host')


def raise_timeout(signum, frame):
    raise TimeoutError
