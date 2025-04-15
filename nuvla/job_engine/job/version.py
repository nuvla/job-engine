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

def _compute_version_min(engine_version_tuple: tuple):
    if engine_version_tuple[0] < 2:
        return 0, 0, 1
    else:
        return 1, 0, 0

class JobVersionBiggerThanEngine(Exception):
    pass

class JobVersionIsNoMoreSupported(Exception):
    pass

class Version(object):
    engine_version_str = _get_version_from_env() or _get_version_from_package()
    engine_version = None
    engine_version_min_support = None
    engine_version_min_support_str = None
    if engine_version_str:
        engine_version = _version_to_tuple(engine_version_str)
        engine_version_min_support = _compute_version_min(engine_version)
        engine_version_min_support_str = '.'.join(map(str, engine_version_min_support))

    @classmethod
    def job_version_check(cls, job_version_str: str):
        job_version = _version_to_tuple(job_version_str)

        if cls.engine_version is None:
            logger.warning("Job-Engine version is not known. Ignoring version checks")
            return

        if job_version < cls.engine_version_min_support:
            raise JobVersionIsNoMoreSupported()
        elif job_version > cls.engine_version:
            raise JobVersionBiggerThanEngine()
