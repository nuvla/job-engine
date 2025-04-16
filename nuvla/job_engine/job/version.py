import importlib_metadata
import logging
import os
import re

logger = logging.getLogger(__name__)

VERSION_TRIM_RE = re.compile(r'\.?[^.0-9]+[0-9]*$')

def _get_version_from_env():
    return os.getenv('JOB_ENGINE_VERSION')

def _get_version_from_package():
    try:
        return importlib_metadata.version("nuvla-job-engine")
    except importlib_metadata.PackageNotFoundError:
        logger.warning('Cannot retrieve Job-engine version')
        return None

def _version_to_tuple(engine_version_str: str) -> tuple:
    ver_ = list(map(int, VERSION_TRIM_RE.sub('', engine_version_str).split('.')))
    if len(ver_) < 2:
        return ver_[0], 0, 0
    return tuple(ver_)

class JobVersionNotYetSupported(Exception):
    pass

class JobVersionIsNoMoreSupported(Exception):
    pass

class Version(object):
    engine_version_str = _get_version_from_env() or _get_version_from_package()
    engine_version = None
    if engine_version_str:
        engine_version = _version_to_tuple(engine_version_str)

    @classmethod
    def job_version_check(cls, job_version_str: str):
        job_version = _version_to_tuple(job_version_str)
        if job_version[0] < 2:
            raise JobVersionIsNoMoreSupported()
        elif job_version[0] > 3:
            raise JobVersionNotYetSupported()
