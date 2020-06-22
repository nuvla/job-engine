# -*- coding: utf-8 -*-

import requests
import logging
from .connector import Connector, should_connect
from .utils import create_tmp_file


class NuvlaBoxConnector(Connector):
    def __init__(self, **kwargs):
        super(NuvlaBoxConnector, self).__init__(**kwargs)

        self.api = kwargs.get("api")
        self.job = kwargs.get("job")
        self.ssl_file = None
        self.nuvlabox_api = requests.Session()
        self.nuvlabox_api.verify = False
        self.nuvlabox_api.headers = {'Content-Type': 'application/json',
                                     'Accept': 'application/json'}

        self.nuvlabox_id = kwargs.get("nuvlabox_id")
        self.nuvlabox = None
        self.timeout = 60
        self.acl = None

    @property
    def connector_type(self):
        return 'nuvlabox'

    def get_nuvlabox_api_endpoint(self):
        nb_status = self.api.get(self.nuvlabox.get("nuvlabox-status")).data

        return nb_status.get("nuvlabox-api-endpoint")

    def get_credential(self):
        infra_service_groups = self.api.search('infrastructure-service-group',
                                               filter='parent="{}"'.format(self.nuvlabox.get("id")),
                                               select='id').resources

        cred_subtype = "infrastructure-service-swarm"

        for infra_service_group in infra_service_groups:

            infra_service_group_id = infra_service_group.id

            isg = self.api.get(infra_service_group_id).data

            service_hrefs = isg.get('infrastructure-services')
            for service_href in service_hrefs:
                service_id = service_href.get('href')
                infra_service = self.api.get(service_id).data
                if infra_service.get("subtype") == 'swarm':
                    credentials = self.api.search('credential',
                                                  filter='parent="{}" and subtype="{}"'.format(
                                                      service_id,
                                                      cred_subtype)).resources

                    return credentials[0].data

    def setup_ssl_credentials(self):
        credential = self.get_credential()
        try:
            secret = credential['cert'] + '\n' + credential['key']
        except KeyError:
            logging.error(
                "Credential for {} is either missing or incomplete".format(self.nuvlabox.get("id")))
            raise

        self.ssl_file = create_tmp_file(secret)
        self.nuvlabox_api.cert = self.ssl_file.name

        return True

    def extract_vm_id(self, vm):
        pass

    def extract_vm_ip(self, services):
        pass

    def extract_vm_ports_mapping(self, vm):
        pass

    def extract_vm_state(self, vm):
        pass

    def connect(self):
        logging.info('Connecting to NuvlaBox {}'.format(self.nuvlabox_id))
        self.nuvlabox = self.api.get(self.nuvlabox_id).data
        self.acl = self.nuvlabox.get('acl')

    def clear_connection(self, connect_result):
        if self.ssl_file:
            self.ssl_file.close()
            self.ssl_file = None

    @should_connect
    def start(self, **kwargs):
        self.job.set_progress(10)

        # 1st - get the NuvlaBox Mgmt API endoint
        nb_api_endpoint = self.get_nuvlabox_api_endpoint()
        if nb_api_endpoint:
            self.job.set_progress(50)
        else:
            msg = "NuvlaBox {} missing API endpoint in its status resource".format(self.nuvlabox.get("id"))
            logging.warning(msg)
            raise Exception(msg)

        # 2nd - get the corresponding credential and prepare the SSL environment
        self.setup_ssl_credentials()

        self.job.set_progress(90)
        action_endpoint = '{}/{}'.format(nb_api_endpoint,
                                         kwargs.get('api_action_name', '')).rstrip('/')

        method = kwargs.get('method', 'GET').upper()
        payload = kwargs.get('payload', {})
        headers = kwargs.get('headers', None)

        # 3rd - make the request
        r = self.nuvlabox_api.request(method, action_endpoint, json=payload, headers=headers,
                                      timeout=self.timeout)

        r.raise_for_status()

        self.job.set_progress(95)

        return r.json()

    @should_connect
    def stop(self, **kwargs):
        pass

    # @should_connect
    def update(self, payload, **kwargs):
        """ Updates the NuvlaBox resource with the provided payload

        :param payload: content to be updated in the NuvlaBox resource
        """

        if payload:
            self.api.edit(self.nuvlabox_id, payload)

        self.job.set_progress(100)

    def list(self):
        pass
