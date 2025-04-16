import importlib_metadata
import logging
import os
import re

logger = logging.getLogger(__name__)

VERSION_TRIM_RE = re.compile(r'\.?[^.0-9]+[0-9]*$')

_SUPPORTED_VERSION = 2

def _get_version_from_env():
    return os.getenv('JOB_ENGINE_VERSION')

def _get_version_from_package():
    try:
        return importlib_metadata.version("nuvla-job-engine")
    except importlib_metadata.PackageNotFoundError:
        logger.warning('Cannot retrieve Job-engine version')
        return None

class JobVersionNotYetSupported(Exception):
    pass

class JobVersionIsNoMoreSupported(Exception):
    pass

class Version(object):
    engine_version = _get_version_from_env() or _get_version_from_package()

    @classmethod
    def job_version_check(cls, job_version_str: str):
        try:
            job_version = int(job_version_str)
        except ValueError:
            job_version = 0
        if job_version < _SUPPORTED_VERSION:
            raise JobVersionIsNoMoreSupported()
        elif job_version > _SUPPORTED_VERSION:
            raise JobVersionNotYetSupported()
