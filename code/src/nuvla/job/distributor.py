# -*- coding: utf-8 -*-

import sys
import time
import logging

from .base import Base


class Distributor(Base):
    def __init__(self):
        super(Distributor, self).__init__()
        self.collect_interval = None
        self.exit_on_failure = False

    def _job_distributor(self):
        logging.info('I am {} and I have been elected to distribute "{}" jobs'
                     .format(self.name, self._get_jobs_type()))
        while not Base.stop_event.is_set():
            for cimi_job in self.job_generator():
                try:
                    logging.info('Distribute job: {}'.format(cimi_job))
                    self.api.add('job', cimi_job)
                except Exception:
                    logging.error('Failed to distribute job: {}.'.format(cimi_job))
                    time.sleep(0.1)
                    if self.exit_on_failure:
                        exit(1)
            time.sleep(self.collect_interval)
        logging.info('Distributor properly stopped.')
        sys.exit(0)

    def _start_distribution(self):
        election = self._kz.Election('/election/{}'.format(self._get_jobs_type()), self.name)
        while True:
            logging.info('STARTING ELECTION')
            election.run(self._job_distributor)

    # ----- METHOD THAT CAN/SHOULD BE IMPLEMENTED IN DISTRIBUTOR SUBCLASS -----
    def job_generator(self):
        """This is a generator function that produces a sequence of Job(s) to be added to the nuvla
        server. This function must be overridden by the user subclass.
        """
        raise NotImplementedError()

    def _get_jobs_type(self):
        raise NotImplementedError()

    def do_work(self):
        logging.info('I am distributor {}.'.format(self.name))
        self._start_distribution()
