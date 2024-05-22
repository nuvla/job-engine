# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import logging
import os
import re
import signal

from typing import List

from contextlib import contextmanager
from datetime import datetime, timedelta
from subprocess import run, STDOUT, PIPE, TimeoutExpired, CompletedProcess
from tempfile import NamedTemporaryFile

log = logging.getLogger('connector_utils')
log.setLevel(logging.DEBUG)

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


def unique_id_short(*args, take=8):
    return hashlib.sha256(':'.join(map(str, args)).encode()).hexdigest()[:take]


def md5sum(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


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
        log.error('Error executing command: %s', result)
        raise Exception(result.stderr)


def join_stderr_stdout(process_result: CompletedProcess):
    return f'StdOut: \n{process_result.stdout} \n\nStdErr: \n{process_result.stderr}'


def create_tmp_file(content, delete=True):
    file = NamedTemporaryFile(delete=delete)
    file.write(content.encode())
    file.flush()
    return file


def string_interpolate_env_vars(string: str, env: dict) -> str:
    envsubst_shell_format = ' '.join([f'${k}' for k in env.keys()])
    cmd = ['envsubst', envsubst_shell_format]
    return execute_cmd(cmd, env=env, input=string).stdout


def store_files(files, directory_path='.'):
    for file_info in files:
        file_path = os.path.join(directory_path, file_info['file-name'])
        f = open(file_path, 'w')
        f.write(file_info['file-content'])
        f.close()


def interpolate_and_store_files(env: dict, files: List[dict]):
    files_store = []
    for file in files or []:
        content = string_interpolate_env_vars(file['file-content'], env)
        files_store.append({'file-name': file['file-name'],
                            'file-content': content})
    store_files(files_store)


def to_base64(s: str, encoding='utf-8') -> str:
    return base64.b64encode(s.encode(encoding)).decode(encoding)


def from_base64(s: str, encoding='utf-8') -> str:
    return base64.b64decode(s.encode(encoding)).decode(encoding)


def generate_registry_config(registries_auth: list):
    auths = {}
    for registry_auth in registries_auth:
        auth = to_base64(
            registry_auth['username'] + ':' + registry_auth['password'])
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
