# -*- coding: utf-8 -*-

import logging

from ..actions import action


@action('decommission_nuvlabox')
class NuvlaBoxDeleteJob(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.error = 0

    def delete_resource(self, resource_id):
        try:
            self.api.delete(resource_id)
        except Exception:
            self.error += 1
            logging.warning(f'problem deleting resource {resource_id}.')

    def delete_linked_resources(self, collection, parent_id):
        try:
            resources = self.api.search(collection,
                                        filter=f'parent="{parent_id}"',
                                        select='id').resources
            for resource in resources:
                self.delete_resource(resource.id)
        except Exception:
            # An exception when querying is probably caused by the collection
            # not existing. Simply log and ignore this.
            logging.warning('problem querying collection {}.'.format(collection))

    def delete_api_key(self, nuvlabox_id):
        self.delete_linked_resources('credential', nuvlabox_id)

    # FIXME: This will currently leave orphan data-object and data-record resources!
    # FIXME: This will currently leave orphan deployments!
    def delete_credential(self, credential):
        self.delete_resource(credential.id)

    def delete_service(self, service_id):
        self.delete_linked_resources('credential', service_id)
        self.delete_resource(service_id)

    def delete_infra_service_group(self, nuvlabox_id):
        infra_service_groups = self.api.search('infrastructure-service-group',
                                               filter='parent="{}"'.format(nuvlabox_id),
                                               select='id').resources

        for infra_service_group in infra_service_groups:

            isg = self.api.get(infra_service_group.id).data

            service_hrefs = isg.get('infrastructure-services')
            for service_href in service_hrefs:
                service_id = service_href.get('href')
                self.delete_service(service_id)

            self.delete_resource(infra_service_group.id)

    def delete_peripherals(self, nuvlabox_id):
        self.delete_linked_resources('nuvlabox-peripheral', nuvlabox_id)

    def delete_logs(self, nuvlabox_id):
        self.delete_linked_resources('resource-log', nuvlabox_id)

    def delete_status(self, nuvlabox_id):
        self.delete_linked_resources('nuvlabox-status', nuvlabox_id)

    def delete_vpn_cred(self, nuvlabox_id, vpn_server_id):
        credentials = self.api.search('credential',
                                      filter='parent="{}" and vpn-certificate-owner="{}"'
                                      .format(vpn_server_id, nuvlabox_id),
                                      select='id, subtype').resources
        for credential in credentials:
            self.delete_credential(credential)

    def delete_nuvlabox(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('NuvlaBox decommission job started for {}.'.format(nuvlabox_id))

        nuvlabox = self.api.get(nuvlabox_id).data

        self.job.set_progress(10)

        # The state of the nuvlabox must be in 'DECOMMISSIONING' to actually try to
        # delete associated resources. If it is not, then job should terminate correctly
        # but perform no actions.
        if nuvlabox.get('state') == 'DECOMMISSIONING':
            self.delete_status(nuvlabox_id)

            self.job.set_progress(20)

            self.delete_infra_service_group(nuvlabox_id)

            self.job.set_progress(30)

            self.delete_peripherals(nuvlabox_id)

            self.job.set_progress(40)

            self.delete_logs(nuvlabox_id)

            self.job.set_progress(45)

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
