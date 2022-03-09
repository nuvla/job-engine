#!/usr/bin/env python

import unittest
from typing import Dict, Any
from nuvla.job.actions.application_docker_compose_validate import ApplicationDockerComposeValidate


class TestApplicationDockerComposeValidate(unittest.TestCase):

    def test_get_env_to_mute_undefined(self):
        test_input: Dict[str, Any] = {'environmental-variables': [
            {'name': "ENV_1"},
            {'name': "ENV_2"}
        ]}

        expected: Dict[str, str] = {"ENV_1": "", "ENV_2": ""}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {'environmental-variables': [
            {'name': "ENV_1", "value": 50},
            {'name': "ENV_2", "value": "30"}
        ]}
        expected: Dict[str, str] = {"ENV_1": 50, "ENV_2": "30"}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {'environmental-variables': [
            {'name': "ENV_1"},
            {'name': "ENV_2", "value": "30"}
        ]}
        expected: Dict[str, str] = {"ENV_1": "", "ENV_2": "30"}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {}
        expected: Dict[str, str] = {}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {'environmental-variables': [
            {'nam': "ENV_1"},
            {'name': "ENV_2", "value": "30"}
        ]}
        expected: Dict[str, str] = {"ENV_2": "30"}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {'environmental-variables': [
            {'name': " "},
            {'name': "ENV_2", "value": "30"}
        ]}
        expected: Dict[str, str] = {"ENV_2": "30"}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))

        test_input: Dict[str, Any] = {'environmental-variables': [
            {'name': ""},
            {'name': "ENV_2", "value": "30"}
        ]}
        expected: Dict[str, str] = {"ENV_2": "30"}
        self.assertDictEqual(expected, ApplicationDockerComposeValidate.get_env_to_mute_undefined(test_input))
