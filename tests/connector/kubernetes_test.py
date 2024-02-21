import json
import os
import unittest
from datetime import datetime
from mock import Mock

from job_engine.connector.kubernetes import Kubernetes

dir_path = os.path.dirname(os.path.abspath(__file__))

TEST_DATA_PATH = f'{dir_path}/test-data'


def get_all_pods():
    with open(f'{TEST_DATA_PATH}/all-pods.json') as fp:
        return json.load(fp)


def get_replicaset():
    with open(f'{TEST_DATA_PATH}/replicaset-owned-by-deployment.json') as fp:
        return json.load(fp)


def get_all_jobs():
    with open(f'{TEST_DATA_PATH}/all-jobs.json') as fp:
        return json.load(fp)


class TestKubernetesLogs(unittest.TestCase):

    def test_log_timestamp_prepended(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')
        res = k8s.log('a/b', datetime.now(), 0)
        assert isinstance(res, str)
        ts = datetime.utcnow().strftime(Kubernetes.TIMESTAMP_FMT_UTC)
        assert res.startswith(ts.split('T')[0])


REPLICASET_NAME = 'nginx-7585f949b8'


def _validate_pods_deployment(pods_found):
    assert 3 == len(pods_found)
    assert {f'{REPLICASET_NAME}-wkmws',
            f'{REPLICASET_NAME}-stllz',
            f'{REPLICASET_NAME}-kmgwn'} == \
           set([r['metadata']['name'] for r in pods_found])


class TestKubernetesFilterPods(unittest.TestCase):

    def test_filter_owned_pods(self):
        assert [] == Kubernetes._filter_objects_owned([], 'Pod', 'foo', 'bar')

        pods = get_all_pods()

        # non-existent object foo/bar
        assert [] == Kubernetes._filter_objects_owned(pods['items'], 'Pod',
                                                      'foo', 'bar')

        # existent DaemonSet/deamonset object
        pods_found = Kubernetes._filter_objects_owned(pods['items'], 'Pod',
                                                      'DaemonSet', 'daemonset')
        assert 1 == len(pods_found)
        assert 'daemonset-b2wsr' == pods_found[0]['metadata']['name']

    def test_filter_pods_owned_by_replicaset(self):
        pods = get_all_pods()
        # existent ReplicaSet/nginx-7585f949b8 object with 3 Pods
        pods_found = Kubernetes._filter_objects_owned(pods['items'], 'Pod',
                                                      'ReplicaSet',
                                                      REPLICASET_NAME)
        _validate_pods_deployment(pods_found)


class TestGetPods(unittest.TestCase):

    def test_get_pods_deployment(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')

        k8s._exec_stdout_json = Mock(return_value={})
        assert [] == k8s._get_pods_deployment('ns-foo', 'nginx')

        k8s._exec_stdout_json.side_effect = [get_replicaset(),
                                             get_all_pods()]
        pods_found = k8s._get_pods_deployment('all-aps', 'nginx')
        _validate_pods_deployment(pods_found)

    def test_get_pods_cronjob(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')

        k8s._exec_stdout_json = Mock(return_value={})
        assert [] == k8s._get_pods_cronjob('all-apps', 'hello')

        k8s._exec_stdout_json.side_effect = [get_all_jobs(), get_all_pods()]
        pods_found = k8s._get_pods_cronjob('all-aps', 'hello')
        assert 3 == len(pods_found)
        assert {'hello-28140324-srfgb',
                'hello-28140325-6d8jk',
                'hello-28140326-pbq94'} == \
               set([r['metadata']['name'] for r in pods_found])

    def test_get_pods_job(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')

        k8s._exec_stdout_json = Mock(return_value={})
        assert [] == k8s._get_pods_regular('all-apps', 'Job', 'pi')

        k8s._exec_stdout_json = Mock(return_value=get_all_pods())
        pods_found = k8s._get_pods_regular('all-apps', 'Job', 'pi')
        assert 1 == len(pods_found)
        assert {'pi-mx9q6'} == \
               set([r['metadata']['name'] for r in pods_found])

    def test_get_pods_daemonset(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')

        k8s._exec_stdout_json = Mock(return_value={})
        assert [] == k8s._get_pods_regular('all-apps', 'DaemonSet', 'pi')

        k8s._exec_stdout_json = Mock(return_value=get_all_pods())
        pods_found = k8s._get_pods_regular('all-apps', 'DaemonSet', 'daemonset')
        assert 1 == len(pods_found)
        assert {'daemonset-b2wsr'} == \
               set([r['metadata']['name'] for r in pods_found])

    def test_get_pods_statefulset(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')

        k8s._exec_stdout_json = Mock(return_value={})
        assert [] == k8s._get_pods_regular('all-apps', 'StatefulSet', 'pi')

        k8s._exec_stdout_json = Mock(return_value=get_all_pods())
        pods_found = k8s._get_pods_regular('all-apps', 'StatefulSet', 'web')
        assert 2 == len(pods_found)
        assert {'web-0', 'web-1'} == \
               set([r['metadata']['name'] for r in pods_found])
