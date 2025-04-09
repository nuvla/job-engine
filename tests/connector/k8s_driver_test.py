import yaml
import os
import tempfile
import unittest

from nuvla.job_engine.connector.k8s_driver import Kubernetes


class TestK8sKubernetes(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_deployment_context_no_namespace_yaml(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')
        manifest = '''
apiVersion: v1
kind: Namespace
metadata:
  name: test-namespace
'''
        k8s._create_deployment_context(self.temp_dir.name, 'test-namespace', manifest, [])
        # Check if the context was created
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir.name, 'kustomization.yml')))
        with open(os.path.join(self.temp_dir.name, 'kustomization.yml'), 'r') as f:
            k = yaml.safe_load(f)
            self.assertNotIn('namespace.yml', k.get('resources'))

    def test_create_deployment_context_with_namespace_yaml(self):
        k8s = Kubernetes(ca='ca', cert='cert', key='key', endpoint='endpoint')
        manifest = '''
apiVersion: app/v1
kind: Pod
metadata:
  name: test-pod
  namespace: test-namespace
'''
        k8s._create_deployment_context(self.temp_dir.name, 'test-namespace', manifest, [])
        # Check if the context was created
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir.name, 'kustomization.yml')))
        with open(os.path.join(self.temp_dir.name, 'kustomization.yml'), 'r') as f:
            k = yaml.safe_load(f)
            self.assertIn('namespace.yml', k.get('resources'))
