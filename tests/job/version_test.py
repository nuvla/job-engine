import os
import unittest
import importlib
from unittest.mock import patch
import nuvla.job_engine.job.version as version

class VersionTestCase(unittest.TestCase):

    def test_env_version_not_set(self):
        importlib.reload(version)
        self.assertIsNone(version.Version.engine_version_str)
        self.assertIsNone(version.Version.engine_version)
        self.assertIsNone(version.Version.engine_version_min_support)
        self.assertIsNone(version.Version.engine_version_min_support_str)

    @patch.dict(os.environ, {'JOB_ENGINE_VERSION': '2.8.7'})
    def test_env_version_only_set(self):
        importlib.reload(version)
        self.assertEqual(version.Version.engine_version_str, '2.8.7')
        self.assertEqual(version.Version.engine_version, (2, 8, 7))
        self.assertEqual(version.Version.engine_version_min_support, (1, 0, 0))
        self.assertEqual(version.Version.engine_version_min_support_str, '1.0.0')

    @patch('importlib_metadata.version', return_value='2.1.3')
    def test_env_version_not_set_package_set(self, _mock):
        importlib.reload(version)
        self.assertEqual(version.Version.engine_version_str, '2.1.3')
        self.assertEqual(version.Version.engine_version, (2, 1, 3))
        self.assertEqual(version.Version.engine_version_min_support, (1, 0, 0))

    @patch.dict(os.environ, {'JOB_ENGINE_VERSION': '2.8.7'})
    @patch('importlib_metadata.version', return_value='2.1.3')
    def test_env_version_preferred_over_package(self, _mock):
        importlib.reload(version)
        self.assertEqual(version.Version.engine_version_str, '2.8.7')
        self.assertEqual(version.Version.engine_version, (2, 8, 7))
        self.assertEqual(version.Version.engine_version_min_support, (1, 0, 0))

    @patch.dict(os.environ, {})
    @patch('importlib_metadata.version', return_value='2.1.3')
    def test_env_version_empty_package_version_set(self, _mock):
        importlib.reload(version)
        self.assertEqual(version.Version.engine_version_str, '2.1.3')
        self.assertEqual(version.Version.engine_version, (2, 1, 3))
        self.assertEqual(version.Version.engine_version_min_support, (1, 0, 0))

    @patch.dict(os.environ, {'JOB_ENGINE_VERSION': '2.8.7'})
    def test_check_version(self):
        importlib.reload(version)
        self.assertIsNone(version.Version.job_version_check('2.8.7'))
        self.assertIsNone(version.Version.job_version_check('1.0.1'))
        self.assertIsNone(version.Version.job_version_check('1.0.1.dev'))
        self.assertIsNone(version.Version.job_version_check('1.0.1-dev'))
        self.assertIsNone(version.Version.job_version_check('1'))
        with self.assertRaises(version.JobVersionIsNoMoreSupported):
            version.Version.job_version_check('0.0.1')
        with self.assertRaises(version.JobVersionIsNoMoreSupported):
            version.Version.job_version_check('0.1.1')
        with self.assertRaises(version.JobVersionBiggerThanEngine):
            version.Version.job_version_check('2.8.8')

    def test_check_engine_version_not_set(self):
        importlib.reload(version)
        # assert that check version does nothing when no engine version was set
        self.assertIsNone(version.Version.engine_version_str)
        self.assertIsNone(version.Version.job_version_check('2.8.7'))
        self.assertIsNone(version.Version.job_version_check('1.0.1'))
        self.assertIsNone(version.Version.job_version_check('0.0.1'))
