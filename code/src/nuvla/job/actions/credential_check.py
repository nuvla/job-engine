# -*- coding: utf-8 -*-

import logging

from ...connector import docker_stack, kubernetes, utils
from ..actions import action

action_name = 'credential_check'

log = logging.getLogger(action_name)


def is_swarm_enabled_and_manager(info):
    swarm_enabled = None
    is_manager = None
    
    try:
        swarm = info.get('Swarm', {})
        node_id = swarm.get('NodeID')
        swarm_enabled = bool(node_id)
        remote_managers = swarm.get('RemoteManagers')
        
        if swarm_enabled and remote_managers:
            managers = [m.get('NodeID') for m in remote_managers]
            is_manager = node_id in managers
    except (AttributeError, KeyError, TypeError):
        log.exception(f'Failed to fully determine swarm status ({swarm_enabled}, {is_manager}) with: {info}')
    
    return swarm_enabled, (swarm_enabled and is_manager)


def docker_info_error_msg_infer(error_msg):
    error_msg_lowercase = error_msg.lower()
    if any(error_substr in error_msg_lowercase
           for error_substr in ['unable to resolve docker endpoint',
                                'invalid bind address format',
                                'cannot connect to the docker daemon at',
                                'is the docker daemon running',
                                'no such host']):
        # "unable to resolve docker endpoint: Invalid bind address format"
        # it means that the infrastructure has a broken endpoint
        # and will never work -> thus offline

        # "Cannot connect to the Docker daemon at ... Is the docker daemon running?"
        # it means that the infrastructure is reachable,
        # but not the Docker API -> thus offline

        # dial tcp: lookup swarm.nuvdla.io on ...: no such host
        # it means the endpoint is unreachable and thus not usable -> offline
        return False, 'UNKNOWN'
    elif any(error_substr in error_msg_lowercase
             for error_substr in ['remote error: tls',
                                  'seems invalid']):
        # "error during connect: Get <endpoint>/v1.40/info:
        # remote error: tls: unknown certificate authority"
        # in this case the infra is running, reachable, and Docker has replied.
        # Simply the creds are not good
        return True, 'INVALID'
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
        return None, 'UNKNOWN'


def k8s_info_error_msg_infer(error_msg):
    error_msg_lowercase = error_msg.lower()
    cert_errors = [
        'failed to parse',  # creds are malformed.
        'syntax error',  # creds are malformed.
        'does not match',  # key doesn't match cert.
        'must be logged in to the server'  # server doesn't recognise creds.
    ]
    cert_problems = [error in error_msg_lowercase for error in cert_errors]
    server_errors = [
        'notfound',  # requested resource on server not found.
        'unable to connect to the server',
        'command execution timed out',
        'server rejected our request'
    ]
    server_problems = [error in error_msg_lowercase for error in server_errors]
    if any(cert_problems):
        # Were we able to reach endpoint. The problem is highly likely
        # with credentials.
        return True, "INVALID"
    elif any(server_problems):
        return False, "UNKNOWN"
    # In all other cases, we don't know.
    return None, "UNKNOWN"


def update_changed(body, infra_service, k, v):
    if v != infra_service.get(k) and v is not None:
        body[k] = v
    return body


@action(action_name)
class CredentialCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def check_coe_swarm(self, credential, infra_service):
        connector = docker_stack.instantiate_from_cimi(infra_service, credential)
        info = connector.info()
        self.job.set_status_message(info)
        return info

    def check_coe_swarm_and_set_infra_attributes(self, credential, infra_service, is_in_pull_mode=None):
        infra_online = None
        swarm_enabled = None
        swarm_manager = None

        if is_in_pull_mode == False:
            endpoint = infra_service.get('endpoint', '')
            if utils.is_endpoint_local(endpoint):
                self.update_credential_last_check(credential["id"], 'UNKNOWN')
                raise Exception('Endpoint is local, cannot check credential, only "pull" mode can be used.')

        try:
            info = self.check_coe_swarm(credential, infra_service)
            infra_online = True
            swarm_enabled, swarm_manager = is_swarm_enabled_and_manager(info)
        except Exception as ex:
            error_msg = ex.args[0]
            infra_online, cred_validity = docker_info_error_msg_infer(error_msg)
            self.update_credential_last_check(credential["id"], cred_validity)
            raise Exception(error_msg)
        finally:
            body = {}
            update_changed(body, infra_service, 'online', infra_online)
            update_changed(body, infra_service, 'swarm-enabled', swarm_enabled)
            update_changed(body, infra_service, 'swarm-manager', swarm_manager)
            if body:
                self.api.edit(infra_service.get("id"), body)

    def check_coe_k8s_and_set_infra_attributes(self, credential, infra_service):
        infra_online = None
        try:
            info = self.check_coe_kubernetes(credential, infra_service)
            if info.get('serverVersion'):
                infra_online = True
        except Exception as ex:
            error_msg = ex.args[0]
            infra_online, cred_validity = k8s_info_error_msg_infer(error_msg)
            self.update_credential_last_check(credential["id"], cred_validity)
            raise Exception(error_msg)
        finally:
            body = {}
            update_changed(body, infra_service, 'online', infra_online)
            if body:
                self.api.edit(infra_service.get("id"), body)

    def check_coe_kubernetes(self, credential, infra_service):
        connector = kubernetes.instantiate_from_cimi(infra_service, credential)
        version = connector.version()
        self.job.set_status_message(version)
        return version

    def check_registry_login(self, credential, infra_service):
        try:
            docker_stack.DockerStack.registry_login(
                username=credential['username'],
                password=credential['password'],
                serveraddress=infra_service['endpoint'])
        except:
            self.update_credential_last_check(credential["id"], 'INVALID')
            raise

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
                self.check_coe_swarm_and_set_infra_attributes(credential, infra_service, self.job.is_in_pull_mode)
            elif infra_service_subtype == 'kubernetes':
                self.check_coe_k8s_and_set_infra_attributes(credential, infra_service)
            elif infra_service_subtype == 'registry':
                self.check_registry_login(credential, infra_service)
            self.update_credential_last_check(credential_id, 'VALID')
        except Exception as ex:
            log.error('Failed to {0} {1}: {2}'.format(self.job['action'], infra_service_id, ex))
            msg = str(ex)
            lines = msg.splitlines()
            status = lines[-1] if len(lines) > 1 else msg
            self.job.set_status_message(status)
            return 1

        return 0
