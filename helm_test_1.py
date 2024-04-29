#!/usr/bin/env python3

from nuvla.job_engine.connector.kubernetes import HelmAppMgmt
import nuvla.job_engine.connector.kubernetes as k8s

k8s.NUVLAEDGE_SHARED_PATH = '.'


def main():
    ham = HelmAppMgmt()

    ham.start(env=[], files=[],
              helm_repo_url='https://helm.github.io/examples',
              helm_chart_name='hello-world')


if __name__ == '__main__':
    main()
