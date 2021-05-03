# -*- coding: utf-8 -*-

import logging

from ..actions import action


@action('decommission_nuvlabox')
class NuvlaBoxDeleteJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.error = 0

    def delete_linked_resources(self, collection, nuvlabox_id):
        try:
            entries = self.api.search(collection,
                                      filter='parent="{}"'.format(nuvlabox_id),
                                      select='id').resources
            for entry in entries:
                entry_id = entry.id
                try:
                    self.api.delete(entry.id)
                except Exception:
                    self.error += 1
                    logging.warning('problem deleting resource {}.'.format(entry_id))
        except Exception:
            # An exception when querying is probably caused by the collection
            # not existing. Simply log and ignore this.
            logging.warning('problem querying collection {}.'.format(collection))

    def delete_api_key(self, nuvlabox_id):
        self.delete_linked_resources('credential', nuvlabox_id)

    # FIXME: This will currently leave orphan data-object and data-record resources!
    def delete_s3_credential(self, credential_id):
        # remove all data objects and records with credential

        self.api.delete(credential_id)

    # FIXME: This will currently leave orphan deployments!
    def delete_swarm_credential(self, credential_id):
        # find all active deployments
        # stop all of them
        # wait for deployments to stop
        # delete credential

        self.api.delete(credential_id)

    def delete_credential(self, credential):

        credential_type = credential.get('subtype')
        credential_id = credential.get('id')

        try:
            if credential_type == 'swarm':
                self.delete_swarm_credential(credential_id)
            elif credential_type == 's3':
                self.delete_s3_credential(credential_id)
            else:
                self.api.delete(credential_id)
        except Exception:
            self.error += 1
            logging.warning('problem deleting resource {}.'.format(credential_id))

    def delete_service(self, service_id):
        credentials = self.api.search('credential',
                                      filter='parent="{}"'.format(service_id),
                                      select='id, subtype').resources

        for credential in credentials:
            self.delete_credential(credential.data)

        try:
            self.api.delete(service_id)
        except Exception:
            self.error += 1
            logging.warning('problem deleting resource {}.'.format(service_id))

    def delete_infra_service_group(self, nuvlabox_id):
        infra_service_groups = self.api.search('infrastructure-service-group',
                                               filter='parent="{}"'.format(nuvlabox_id),
                                               select='id').resources

        for infra_service_group in infra_service_groups:

            infra_service_group_id = infra_service_group.id

            isg = self.api.get(infra_service_group_id).data

            service_hrefs = isg.get('infrastructure-services')
            for service_href in service_hrefs:
                service_id = service_href.get('href')
                self.delete_service(service_id)

            try:
                self.api.delete(infra_service_group_id)
            except Exception:
                self.error += 1
                logging.warning('problem deleting resource {}.'.format(infra_service_group_id))

    def delete_peripherals(self, nuvlabox_id):
        # If the nuvlabox-peripheral collection doesn't exist, then this acts as a no-op.
        self.delete_linked_resources('nuvlabox-peripheral', nuvlabox_id)

    def delete_status(self, nuvlabox_id):
        self.delete_linked_resources('nuvlabox-status', nuvlabox_id)

    def delete_vpn_cred(self, nuvlabox_id, vpn_server_id):
        credentials = self.api.search('credential',
                                      filter='parent="{}" and vpn-certificate-owner="{}"'
                                      .format(vpn_server_id, nuvlabox_id),
                                      select='id, subtype').resources
        for credential in credentials:
            self.delete_credential(credential.data)

    def delete_nuvlabox(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('NuvlaBox decommission job started for {}.'.format(nuvlabox_id))

        nuvlabox = self.api.get(nuvlabox_id).data

        self.job.set_progress(10)

        # The state of the nuvlabox must be in 'DECOMMISSIONING' to actually try to
        # delete associated resources.  If it is not, then job should terminate correctly
        # but perform no actions.
        if nuvlabox.get('state') == 'DECOMMISSIONING':
            self.delete_status(nuvlabox_id)

            self.job.set_progress(20)

            self.delete_infra_service_group(nuvlabox_id)

            self.job.set_progress(30)

            self.delete_peripherals(nuvlabox_id)

            self.job.set_progress(40)

            self.delete_api_key(nuvlabox_id)

            self.job.set_progress(50)

            vpn_server_id = nuvlabox.get('vpn-server-id')

            if vpn_server_id:
                self.delete_vpn_cred(nuvlabox_id, vpn_server_id)

            self.job.set_progress(60)

            if self.error == 0:
                try:
                    self.api.edit(nuvlabox_id, {"state": "DECOMMISSIONED"}, select='online')
                except Exception:
                    self.error += 1
                    logging.warning('problem updating nuvlabox resource: {}'.format(nuvlabox_id))

        return self.error

    def do_work(self):
        return self.delete_nuvlabox()
