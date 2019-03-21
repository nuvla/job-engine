# -*- coding: utf-8 -*-

import logging
import shutil
import os
import base64
import machine as DockerMachine

from .connector import Connector, should_connect


def instantiate_from_cimi(api_infrastructure_service, api_credential):
    return DockerMachineConnector(driver_credential=api_credential,
                            driver=api_credential["type"].split("-")[-1],
                            service_owner=api_infrastructure_service['acl']['owner']['principal'],
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

    DOCKER_MACHINE_FOLDER = "/root/.docker/machine/machines"

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
        self.local_conf_dir = "{}/{}".format(self.DOCKER_MACHINE_FOLDER, self.machineBaseName)
        self.multiplicity = self.kwargs.get("multiplicity", 1)
        self.service_owner = self.kwargs["service_owner"]
        self.machine = DockerMachine.Machine()

    @property
    def connector_type(self):
        return 'docker-machine'

    def connect(self):
        version = self.machine.version()
        logging.info("Initializing a local docker-machine. Version: %s" % version)

    @staticmethod
    def delete_folder(path):
        shutil.rmtree(path)
        return

    def clear_connection(self, connect_result=None):
        try:
            self.delete_folder(self.local_conf_dir)
        except FileNotFoundError:
            pass

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

    def _get_node(self):
        with open("{}/config.json".format(self.local_conf_dir), 'r') as file:
            b64_content = base64.b64encode(file.read().encode('ascii'))

        node = {
            "machine-name": self.machineBaseName,
            "machine-config-base64": b64_content.decode("ascii")
        }

        return node

    def install_swarm(self):
        command = "sudo docker swarm init --force-new-cluster --advertise-addr {}".format(self._vm_get_ip())
        start_swarm = self.machine.ssh(self.machineBaseName, command)

        return start_swarm

    @staticmethod
    def load_file_content(path):
        with open(path, 'r') as file:
            content = file.read()

        return content

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

        self.install_swarm()

        new_coe = {
            "credential": self.create_swarm_credential_payload(self.service_owner),
            "ip": self._vm_get_ip(),
            "node": self._get_node()
        }

        return new_coe

    @should_connect
    def stop(self, ids):
        stopped = []
        for node in ids:
            machine_folder = "{}/{}".format(self.DOCKER_MACHINE_FOLDER, node["machine-name"])
            os.makedirs(machine_folder)

            with open("{}/config.json".format(machine_folder), 'w') as cfg:
                cfg.write( base64.b64decode( node["machine-config-base64"].encode('ascii') ).decode('ascii') )

            stopped.append(self.machine.rm(machine=self.machineBaseName, force=True))

        return stopped

    def list(self):
        self.machine.ls()
