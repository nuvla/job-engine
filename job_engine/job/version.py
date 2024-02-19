from importlib_metadata import version, PackageNotFoundError


package_name = "nuvla-job-engine"
try:
    version = version(package_name)
except PackageNotFoundError:
    version = None
