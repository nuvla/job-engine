# -*- coding: utf-8 -*-

import logging
import time


class DistributionBase():
    def __init__(self, distribution_name, distributor):
        self.distribution_name = distribution_name
        self.collect_interval = 60  # one per minute
        self.distributor = distributor

    def _get_sleep_time(self):
        dist_interval = self.distributor.args.distribution_interval
        for i in range(len(dist_interval)):
            if dist_interval[i].startswith(f'{self.distribution_name}:'):
                try:
                    return int(dist_interval[i].split(':')[1])
                except ValueError:
                    logging.error(f'Bad argument: distribution_interval should be an integer')
                    exit(1)
        return self.collect_interval

    def _job_distribution(self):
        sleep_time = self._get_sleep_time()
        logging.info(f'I am {self.distributor.name} and I have been elected '
                     f'to distribute "{self.distribution_name}" jobs every {sleep_time}s')
        while not self.distributor.stop_event.is_set():
            try:
                for cimi_job in self.job_generator():
                    logging.info(f'Distribute job: {cimi_job}')
                    self.distributor.api.add('job', cimi_job)
                time.sleep(sleep_time)
            except Exception as ex:
                logging.error(f'Failed to distribute job {self.distribution_name}: {ex}')
                time.sleep(5)

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
