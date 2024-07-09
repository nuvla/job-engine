import importlib_metadata
import logging
import os

logger = logging.getLogger(__name__)

package_name = "nuvla-job-engine"
version = os.getenv('JOB_ENGINE_VERSION')
if not version:
    try:
        version = importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        logger.warning('Cannot retrieve Job-engine version')
        version = None
