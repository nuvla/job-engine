# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
import requests
import machine as DockerMachine

from .connector import Connector, should_connect

import time
from tempfile import NamedTemporaryFile
import re
from exceptions import Exception, RuntimeError


class DockerMachineConnector(Connector):

    def __init__(self, api_infrastructure, api_credential, api_endpoint=None):
        super(DockerMachineConnector, self).__init__(api_infrastructure, api_credential)
        self.api_infrastructure = self.api_connector

        # Nuvla managed or self-managed

        # if Nuvla-managed, what's the driver

        # all keys, for both client and server

        # credentials to deploy the docker-machine

        # endpoint

        self.docker_api = requests.Session()
        self.docker_api.verify = False
        self.docker_api.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        self.machine = None

        # user given name for the machine/service
        self.serviceName
    @property
    def connector_type(self):
        return 'docker-machine'

    def connect(self):
        logging.info('Initializing a local docker-machine object')
        return DockerMachine.Machine()

    def clear_connection(self):
        # delete the local .docker machine cache
        pass

    def _get_full_url(self):
        return self.machine.url(machine=self.serviceName)

    @staticmethod
    def validate_action(response):
        """Takes the raw response from _start_container_in_docker
        and checks whether the service creation request was successful or not"""
        pass


    def _vm_get_ip(self):
        return self.machine.ip(machine=self.serviceName)

    def _vm_get_id(self):
        pass

    def _vm_get_state(self):
        pass

    @should_connect
    def start(self, api_deployment):
        logging.info('start docker-machine')
        pass

    @should_connect
    def stop(self, ids):
        logging.info('stop docker-machine')
        # remember to retrieve config and certs from service resource
        pass

    @should_connect
    def list(self):
        self.machine.ls()
