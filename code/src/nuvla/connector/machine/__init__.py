# Forked from python-docker-machine==0.2.5
# Changes:
#  - allow to provide environment variables to docker-machine.
#

import pkg_resources
from .machine import Machine


try:
    __version__ = pkg_resources.require("python-docker-machine")[0].version
except pkg_resources.DistributionNotFound:
    __version__ = "devel"
