# -*- coding: utf-8 -*-

import logging
import requests
import machine as DockerMachine

from .connector import Connector, should_connect

import time
from tempfile import NamedTemporaryFile
import re
from exceptions import Exception, RuntimeError


class DockerMachineConnector(Connector):

    def __init__(self, api_infrastructure_service, api_service_credential):
        super(DockerMachineConnector, self).__init__(api_infrastructure_service, api_service_credential)

        self.state = api_infrastructure_service.get("state")
        self.driver_credential = api_service_credential
        self.driver = api_infrastructure_service.get("cloud-service")

        self.machine = DockerMachine.Machine()

        # for now
        self.machineBaseName = api_infrastructure_service.get("id")

        self.multiplicity = api_infrastructure_service.get("multiplicity", 1)

    @property
    def connector_type(self):
        return 'docker-machine'

    def connect(self):
        version = self.machine.version()
        logging.info("Initializing a local docker-machine. Version: %s" % version)

    def clear_connection(self):
        # the container where this job run will be terminated, thus no cleanup needed
        pass

    def _get_full_url(self):
        return self.machine.url(machine=self.machineBaseName)

    @staticmethod
    def validate_action(response):
        """Takes the raw response from _start_container_in_docker
        and checks whether the service creation request was successful or not"""
        pass

    def _vm_get_ip(self):
        return self.machine.ip(machine=self.machineBaseName)

    def _vm_get_id(self):
        return self.machineBaseName

    def _vm_get_state(self):
        if self.machine.status(machine=self.machineBaseName):
            return "Running"
        else:
            return "Stopped"

    def install_swarm(self):
        # TODO
        # run the docker-machine ssh script to install Docker swarm
        pass

    def create_swarm_credential(self):
        # TODO
        # create a credential resource with the TLS credentials
        pass

    @should_connect
    def start(self, **kwargs):
        logging.info('start docker-machine')

        # TODO
        arguments_string = "flatten --attr values from service credential"

        self.machine.create(driver=self.driver, xarg=arguments_string)

        # TODO
        # get local config.json, extract all important attributes and base64 encode it

        # TODO
        # get machine TLS certificates from local folder

        self.install_swarm()

        self.create_swarm_credential()

    def rebuild_docker_machine_env(self):
        # TODO
        # extract the config.json from the infrastructure service resource
        # and rebuild the local .docker environment
        pass

    @should_connect
    def stop(self, ids):
        self.rebuild_docker_machine_env()

        self.machine.rm(machine=self.machineBaseName)

    def list(self):
        self.machine.ls()
