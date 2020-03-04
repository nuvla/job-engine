# -*- coding: utf-8 -*-
import os
import json
import base64
import hashlib
from datetime import datetime, timedelta
from subprocess import run, PIPE, STDOUT, TimeoutExpired
from tempfile import NamedTemporaryFile


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
    return hashlib.md5(':'.join(map(str, args)).encode()).hexdigest()


def append_os_env(env):
    final_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if value:
                final_env[key] = value
    return final_env


def execute_cmd(cmd, **kwargs):
    print(kwargs)
    if kwargs.get('noenv'):
        opt_env = None
    else:
        opt_env = append_os_env(kwargs.get('env'))
    opt_input = kwargs.get('input')
    timeout = kwargs.get('timeout', 120)
    try:
        result = run(cmd, stdout=PIPE, stderr=STDOUT, env=opt_env, input=opt_input,
                     timeout=timeout, encoding='UTF-8')
        print(opt_env)
        print(result)
    except TimeoutExpired:
        raise Exception('Command execution timed out after {} seconds'.format(timeout))
    if result.returncode == 0:
        return result.stdout
    else:
        raise Exception(result.stdout)


def create_tmp_file(content):
    file = NamedTemporaryFile(delete=True)
    file.write(content.encode())
    file.flush()
    return file


def generate_registry_config(registries_auth):
    auths = {}
    for registry_auth in registries_auth:
        user_pass = registry_auth['username'] + ':' + registry_auth['password']
        auth = base64.b64encode(user_pass.encode('ascii')).decode('utf-8')
        auths['https://' + registry_auth['serveraddress']] = {'auth': auth}
    return json.dumps({'auths': auths})
