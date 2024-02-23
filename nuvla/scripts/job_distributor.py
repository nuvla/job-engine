#!/usr/bin/env python
# -*- coding: utf-8 -*-

from nuvla.job_engine.job.base import main
from nuvla.job_engine.job.distributor.distributor import Distributor

if __name__ == '__main__':
    main(Distributor)