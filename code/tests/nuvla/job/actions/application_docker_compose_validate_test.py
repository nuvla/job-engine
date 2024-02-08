#!/usr/bin/env python

import unittest
from nuvla.job.actions.application_docker_compose_validate import \
    ApplicationDockerComposeValidate


def clean_return(ret: dict):
    ret.pop('NUVLA_DEPLOYMENT_ID')
    ret.pop('NUVLA_DEPLOYMENT_UUID')
    ret.pop('NUVLA_DEPLOYMENT_UUID')
    ret.pop('NUVLA_DEPLOYMENT_GROUP_ID')
    ret.pop('NUVLA_DEPLOYMENT_GROUP_UUID')
    ret.pop('NUVLA_API_KEY')
    ret.pop('NUVLA_API_SECRET')
    ret.pop('NUVLA_ENDPOINT')
    return ret


class TestApplicationDockerComposeValidate(unittest.TestCase):

    def test_get_env_to_mute_undefined(self):
        tested_function = \
            ApplicationDockerComposeValidate.get_env_to_mute_undefined
        volumes = ['$VOL_1:$VOL_2']

        # Single service only with volumes defined
        single_srvc_yml = {
            'services': {
                'socat': {
                    'volumes': volumes
                }
            },
        }
        single_service_content = {
            'docker-compose': str(single_srvc_yml),
            'environmental-variables':
                [{'name': 'VOL_1', 'required': False},
                 {'name': 'VOL_2', 'required': False}]
        }
        # Non ports should be asxigned a path-type string
        for env_name, value in clean_return(tested_function(
                single_service_content)).items():
            self.assertFalse(value.isnumeric())

        # Multiple service with volumes defined
        single_srvc_yml = {
            'services': {
                'socat': {
                    'volumes': volumes
                },
                'tcl': {
                    'volumes': [
                        '$VOL_3:$VOL_4'
                    ]
                }
            },
        }
        single_service_content = {
            'docker-compose': str(single_srvc_yml),
            'environmental-variables':
                [{'name': 'VOL_1', 'required': False},
                 {'name': 'VOL_2', 'required': False},
                 {'name': 'VOL_3', 'required': False},
                 {'name': 'VOL_4', 'required': False}]
        }
        for env_name, value in clean_return(
                tested_function(single_service_content)).items():
            self.assertFalse(value.isnumeric())

        text_dict = {
            'version': '3.5',
            'services': {
                'socat': {
                    'image': 'sixsq/socat:latest',
                    'ports': [
                        '${EXPOSED_PORT}:1234'
                    ],
                    'volumes': volumes,
                    'environment': [
                        'DESTINATION=${DESTINATION}',
                        'EXPOSED_PORT=${EXPOSED_PORT}'
                    ]
                }
            },
        }
        module_content = {
            'docker-compose': str(text_dict),
            'environmental-variables':
                [{'name': 'EXPOSED_PORT', 'required': False},
                 {'name': 'DESTINATION', 'required': False},
                 {'name': 'VOL_1', 'required': False},
                 {'name': 'VOL_2', 'required': False}]
        }
        expected_return = {
            'EXPOSED_PORT': '1',
            'DESTINATION': '/path/2/',
            'VOL_1': '/path/3/',
            'VOL_2': '/path/4/'}

        # Check the expected dictionary
        test_return = clean_return(tested_function(module_content))
        self.assertTrue(test_return['EXPOSED_PORT'].isnumeric())
        self.assertEqual(expected_return, test_return)
