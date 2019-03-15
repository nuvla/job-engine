# -*- coding: utf-8 -*-

from __future__ import print_function

import logging
import shutil
import machine as DockerMachine

from .connector import Connector, should_connect


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerMachineConnector(driver_credential=api_credential,
                            driver=api_credential["type"].split("-")[-1],
                            infrastructure_service_id=api_infrastructure_service["id"],
                            machineBaseName=api_infrastructure_service.get("name", api_infrastructure_service["id"].split('/')[1]))

class DockerMachineConnector(Connector):
    XARGS = {
        "exoscale": [
            "exoscale-api-secret-key",
            "exoscale-api-key"
        ],
        "amazonec2": [
            "amazonec2-access-key",
            "amazonec2-secret-key"
        ],
        "azure": [
            "azure-client-id",
            "azure-client-secret",
            "azure-subscription-id"
        ],
        "google": [
            "project-id",
            "private-key-id",
            "private-key",
            "client-email",
            "client-id"
        ]
    }

    def __init__(self, **kwargs):
        super(DockerMachineConnector, self).__init__(**kwargs)

        self.driver = self.kwargs.get("driver")

        if not self.driver in self.XARGS:
            raise NotImplementedError('There are no Docker Machine arguments {} available for driver {}.'
                                        .format(self.XARGS, self.driver))
        else:
            self.driver_xargs = self.XARGS[self.driver]

        self.infrastructure_service_id = self.kwargs["infrastructure_service_id"]
        self.driver_credential = self.kwargs["driver_credential"]
        self.machineBaseName = self.kwargs.get("machineBaseName").replace(" ", "-")
        self.local_conf_dir = "/root/.docker/machine/machines/{}".format(self.machineBaseName)
        self.multiplicity = self.kwargs.get("multiplicity", 1)
        self.machine = DockerMachine.Machine()

    @property
    def connector_type(self):
        return 'docker-machine'

    def connect(self):
        version = self.machine.version()
        logging.info("Initializing a local docker-machine. Version: %s" % version)

    def clear_connection(self, connect_result=None):
        shutil.rmtree(self.local_conf_dir)
        return

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

    @staticmethod
    def load_file_content(path):
        with open(path, 'r') as file:
            content = file.read()

        return content.replace('\n', '\\n')

    def create_swarm_credential_payload(self, credential_owner):
        ca_file = "{}/ca.pem".format(self.local_conf_dir)
        cert_file = "{}/cert.pem".format(self.local_conf_dir)
        key_file = "{}/key.pem".format(self.local_conf_dir)

        payload = {
            "template" : {
                "method": "infrastructure-service-swarm",
                "name": self.machineBaseName,
                "description": "Swarm credential for infrastructure service %s" % self.machineBaseName,
                "type": "infrastructure-service-swarm",
                "resource-type": "credential-template",
                "key": self.load_file_content(key_file),
                "ca": self.load_file_content(ca_file),
                "cert": self.load_file_content(cert_file),
                "infrastructure-services": [
                    self.infrastructure_service_id
                ],
                "acl": {"owner": {"principal": credential_owner,
                                  "type": "USER"},
                        "rules": [{"principal": credential_owner,
                                   "type": "USER",
                                   "right": "MODIFY"}]},
                "href": "credential-template/infrastructure-service-swarm"
            }
        }

        return payload

    def flat_docker_machine_args(self):
        # Get the xargs for this driver, from the credential, and make a
        # flat string to pass to Docker Machine
        cmd_xargs = []
        for attribute in self.driver_xargs:
            value = self.driver_credential.get(attribute, None)
            if value:
                cmd_xargs.extend([
                    "--{}".format(attribute),
                    str(value)
                ])

        return cmd_xargs

    @should_connect
    def start(self, **kwargs):
        logging.info('start docker-machine')

        cmd_xarguments = self.flat_docker_machine_args()

        self.machine.create(self.machineBaseName, driver=self.driver, xarg=cmd_xarguments)

        # TODO
        # get local config.json, extract all important attributes and base64 encode it

        self.install_swarm()

        return 1

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
