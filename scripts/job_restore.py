#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
from kazoo.client import KazooClient, KazooRetry, LockingQueue
from elasticsearch import Elasticsearch


def _init_args_parser():
    parser = argparse.ArgumentParser(description='Restore Nuvla jobs')

    parser.add_argument(
        '--zk-hosts', dest='zk_hosts', default=['zk:2181'], nargs='+', metavar='HOST',
        help='ZooKeeper list of hosts [localhost:port]. (default: zk:2181)')
    parser.add_argument(
        '--es-hosts', dest='es_hosts', default=['es'], nargs='+', metavar='HOST',
        help='Elasticsearch list of hosts [localhost:[port]] (default: [es])')

    return parser.parse_args()


if __name__ == '__main__':
    args = _init_args_parser()
    es = Elasticsearch(args.es_hosts)
    kz = KazooClient(','.join(args.zk_hosts), connection_retry=KazooRetry(max_tries=-1),
                     command_retry=KazooRetry(max_tries=-1), timeout=30.0)
    kz.start()

    queue = LockingQueue(kz, '/job')

    data = es.search(index='nuvla-job', body={
        "query": {"bool": {"should": [{"term": {"state": "QUEUED"}},
                                      {"term": {"state": "RUNNING"}}],
                           "must_not": {"term": {"execution-mode": "pull"}}}},
        "sort": {"created": "asc"},
        "from": 0,
        "size": 10000})

    hits = data['hits']['hits']

    jobs_found = data.get('hits', {}).get('total', {}).get('value', '-')

    if jobs_found > 10000:
        logging.error("Max restoration is fixed to 10'000 jobs")
        exit(1)

    logging.warning('Found {} jobs in QUEUED or RUNNING states.'.format(jobs_found))

    for hit in hits:
        job = hit['_source']
        job_id = job['id']
        job_priority = job.get('priority', 100)
        logging.warning('Put job {} with priority {}'.format(job_id, job_priority))
        queue.put(job_id.encode(), job_priority)

    logging.warning('Restoration finished.')
    exit(0)
