# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_cli_connector, kubernetes_cli_connector
from ..actions import action

action_name = 'credential_check'

log = logging.getLogger(action_name)


def is_swarm_enabled(info):
    try:
        node_id = info['Swarm']['NodeID']
        managers = list(map(lambda x: x['NodeID'], info['Swarm']['RemoteManagers']))
        return node_id and node_id in managers
    except (KeyError, TypeError):
        return False
    except:
        # it's ok if we cannot infer the Swarm mode...so just move on
        pass


def docker_info_error_msg_infer(error_msg):
    error_msg_lowercase = error_msg.lower()
    if error_msg_lowercase in ['unable to resolve docker endpoint',
                               'invalid bind address format',
                               'cannot connect to the docker daemon at',
                               'is the docker daemon running',
                               'no such host']:
        # "unable to resolve docker endpoint: Invalid bind address format"
        # it means that the infrastructure has a broken endpoint
        # and will never work -> thus offline

        # "Cannot connect to the Docker daemon at ... Is the docker daemon running?"
        # it means that the infrastructure is reachable,
        # but not the Docker API -> thus offline

        # dial tcp: lookup swarm.nuvdla.io on ...: no such host
        # it means the endpoint is unreachable and thus not usable -> offline
        return False, False
    elif "remote error: tls" in error_msg_lowercase:
        # "error during connect: Get <endpoint>/v1.40/info:
        # remote error: tls: unknown certificate authority"
        # in this case the infra is running, reachable, and Docker has replied.
        # Simply the creds are not good
        return True, False
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


@action(action_name)
class CredentialCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_coe_swarm(self, credential, infra_service):
        connector = connector_factory(docker_cli_connector, self.api,
                                      credential['id'],
                                      api_infrastructure_service=infra_service)
        info = connector.info()
        self.job.set_status_message(info)
        return info

    def check_coe_swarm_and_set_infra_attributes(self, credential, infra_service):
        infra_online = None
        swarm_enabled = None
        try:
            info = self.check_coe_swarm(credential, infra_service)
            infra_online = True
            swarm_enabled = is_swarm_enabled(info)
        except Exception as ex:
            error_msg = ex.args[0]
            infra_online, swarm_enabled = docker_info_error_msg_infer(error_msg)
            raise Exception(error_msg)
        finally:
            infra_service_update_body = {}
            if infra_online != infra_service.get('online') and infra_online is not None:
                infra_service_update_body['online'] = infra_online
            if swarm_enabled != infra_service.get('swarm-enabled') and swarm_enabled is not None:
                infra_service_update_body['swarm-enabled'] = swarm_enabled
            if len(infra_service_update_body) > 0:
                self.api.edit(infra_service.get("id"), infra_service_update_body)

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
                self.check_coe_swarm_and_set_infra_attributes(credential, infra_service)
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
