# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_cli_connector, kubernetes_cli_connector
from ..actions import action

action_name = 'credential_check'

log = logging.getLogger(action_name)


@action(action_name)
class CredentialCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_coe_swarm(self, credential, infra_service):
        connector = connector_factory(docker_cli_connector, self.api,
                                      credential['id'],
                                      api_infrastructure_service=infra_service)

        infra_online = infra_service.get("online")
        infra_swarm_enabled = infra_service.get("swarm-enabled")
        try:
            info = connector.info()
        except Exception as ex:
            error_msg = ex.args[0]
            if ("unable to resolve docker endpoint" in error_msg.lower()) or \
                    ("invalid bind address format" in error_msg.lower()) or \
                    ("cannot connect to the docker daemon at" in error_msg.lower()) or \
                    ("is the docker daemon running" in error_msg.lower()) or \
                    ("no such host" in error_msg.lower()):
                # "unable to resolve docker endpoint: Invalid bind address format"
                # it means that the infrastructure has a broken endpoint
                # and will never work -> thus offline

                # "Cannot connect to the Docker daemon at ... Is the docker daemon running?"
                # it means that the infrastructure is reachable,
                # but not the Docker API -> thus offline

                # dial tcp: lookup swarm.nuvdla.io on ...: no such host
                # it means the endpoint is unreachable and thus not usable -> offline

                if infra_online:
                    self.api.edit(infra_service.get("id"), {'online': False})
                if infra_swarm_enabled:
                    self.api.edit(infra_service.get("id"), {'swarm-enabled': False})
            elif "remote error: tls" in error_msg.lower():
                # "error during connect: Get <endpoint>/v1.40/info:
                # remote error: tls: unknown certificate authority"
                # in this case the infra is running, reachable, and Docker has replied.
                # Simply the creds are not good
                if not infra_online:
                    self.api.edit(infra_service.get("id"), {'online': True})
            else:
                # other errors can simply mean that the server could not run the command,
                # thus not being Docker related
                # like:
                # "open /tmp/key: no such file or directory" -> server side error
                # "failed to retrieve context tls info: tls:
                # failed to parse private key" -> broken user keys
                # "no valid private key found" -> broken user keys format
                # "failed to retrieve context tls info: tls: private key does not match public key"
                # -> cred mismatch
                # "check if the server supports the requested API version" ->
                # client version incompatibility

                # if we got here, is because the error is most likely not related
                # with the infra, so just raise
                pass

            raise Exception(error_msg)

        if not infra_online:
            self.api.edit(infra_service.get("id"), {'online': True})

        try:
            node_id = info['Swarm']['NodeID']
            managers = list(map(lambda x: x['NodeID'], info['Swarm']['RemoteManagers']))
            if node_id and node_id in managers:
                if not infra_swarm_enabled:
                    self.api.edit(infra_service.get("id"), {'swarm-enabled': True})
            else:
                # The endpoint from infrastructure is not a manager
                log.warning("Infrastructure {} does not have a Swarm manager".format(
                    infra_service.get("id")))
                if infra_swarm_enabled:
                    self.api.edit(infra_service.get("id"), {'swarm-enabled': False})
        except (KeyError, TypeError):
            # then Swarm mode is not enabled
            if infra_swarm_enabled:
                self.api.edit(infra_service.get("id"), {'swarm-enabled': False})
        except:
            # it's ok if we cannot infer the Swarm mode...so just move on
            pass

        self.job.set_status_message(info)

    def check_coe_kubernetes(self, credential, infra_service):
        connector = connector_factory(kubernetes_cli_connector, self.api, credential['id'],
                                      api_infrastructure_service=infra_service)
        version = connector.version()
        self.job.set_status_message(version)

    @staticmethod
    def check_registry_login(credential, infra_service):
        docker_cli_connector.DockerCliConnector.registry_login(
            username=credential['username'],
            password=credential['password'],
            serveraddress=infra_service['endpoint'])

    def update_credential_last_check(self, credential_id, status):
        self.api.edit(credential_id, {'status': status})

    def do_work(self):
        credential_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(credential_id))

        credential = self.api.get(credential_id).data

        infra_service_id = credential['parent']

        infra_service = self.api.get(infra_service_id).data

        self.job.set_progress(10)

        infra_service_subtype = infra_service['subtype']

        try:
            if infra_service_subtype == 'swarm':
                self.check_coe_swarm(credential, infra_service)
            elif infra_service_subtype == 'kubernetes':
                self.check_coe_kubernetes(credential, infra_service)
            elif infra_service_subtype == 'registry':
                CredentialCheck.check_registry_login(credential, infra_service)
            self.update_credential_last_check(credential_id, 'VALID')
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], infra_service_id, ex))
            self.update_credential_last_check(credential_id, 'INVALID')
            msg = str(ex)
            lines = msg.splitlines()
            status = lines[-1] if len(lines) > 1 else msg
            self.job.set_status_message(status)
            return 1

        return 0
