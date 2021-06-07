# -*- coding: utf-8 -*-

import logging
import time


class DistributionBase():
    def __init__(self, distribution_name, distributor):
        self.distribution_name = distribution_name
        self.collect_interval = 60.0  # one per minute
        self.distributor = distributor

    def _job_distribution(self):
        logging.info(f'I am {self.distributor.name} and I have been elected '
                     f'to distribute "{self.distribution_name}" jobs')
        while not self.distributor.stop_event.is_set():
            for cimi_job in self.job_generator():
                try:
                    logging.info(f'Distribute job: {cimi_job}')
                    self.distributor.api.add('job', cimi_job)
                except Exception as ex:
                    logging.error(f'Failed to distribute job {cimi_job}: {ex}')
                    time.sleep(0.1)
            time.sleep(self.collect_interval)

    def _start_distribution(self):
        election = self.distributor.kz.Election(f'/election/{self.distribution_name}', self.distributor.name)
        while True:
            logging.info(f'STARTING ELECTION {self.distribution_name}')
            election.run(self._job_distribution)

    # ----- METHOD THAT CAN BE IMPLEMENTED IN DISTRIBUTOR SUBCLASS -----
    def job_generator(self):
        """This is a generator function that produces a sequence of Job(s) to be added to the nuvla
        server.
        """
        job = {'action': self.distribution_name,
               'target-resource': {'href': 'job'}}
        yield job
