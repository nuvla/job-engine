import importlib_metadata
import logging
import os
import re

logger = logging.getLogger(__name__)

def _get_version_from_env():
    return os.getenv('JOB_ENGINE_VERSION')

def _get_version_from_package():
    try:
        return importlib_metadata.version("nuvla-job-engine")
    except importlib_metadata.PackageNotFoundError:
        logger.warning('Cannot retrieve Job-engine version')
        return None

def _version_to_tuple(engine_version_str: str) -> tuple:
    ver_trim_re = re.compile(r'\.?[^.0-9]+[0-9]*$')
    ver_ = list(map(int, ver_trim_re.sub('', engine_version_str).split('.')))
    if len(ver_) < 2:
        return ver_[0], 0, 0
    return tuple(ver_)

def _compute_version_min(engine_version_tuple: tuple):
    if engine_version_tuple[0] < 2:
        return 0, 0, 1
    elif engine_version_tuple[0] == 4:
        # For job-engine 4.x, we support jobs with version 2.x and 3.x
        return engine_version_tuple[0] - 2, 0, 0
    else:
        return engine_version_tuple[0] - 1, 0, 0

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
        """Skips the job by setting `self.nothing_to_do = True` when the job's
        version is outside of the engine's supported closed range [M-1, M.m.P].
        Where M is major version from semantic version definition M.m.P.
        The job will be removed from the queue and set as failed if the job's
        version is strictly lower than M-1.
        The job will be skipped if its version is strictly greater engine's M.m.P.
        (This can happen for a short while during upgrades when jobs distribution
        gets upgraded before the job engine.)
        """
        job_version = _version_to_tuple(job_version_str)

        if cls.engine_version is None:
            logger.warning("Job-Engine version is not known. Ignoring version checks")
            return

        if job_version < cls.engine_version_min_support:
            raise JobVersionIsNoMoreSupported()
        elif job_version > cls.engine_version:
            raise JobVersionBiggerThanEngine()
