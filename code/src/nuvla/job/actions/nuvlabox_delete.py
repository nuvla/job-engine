# -*- coding: utf-8 -*-

import logging

from ..actions import action


@action('delete_nuvlabox')
class NuvlaBoxDeleteJob(object):
    def __init__(self, executor, job):
        self.job = job
        self.api = job.api

    def delete_api_key(self, nuvlabox_id):
        credentials = self.api.search('credential',
                                      filter='parent="{}"'.format(nuvlabox_id),
                                      select='id').resources

        for credential in credentials:
            self.api.delete(credential.id)

    # FIXME: This will currently leave orphan data-object and data-record resources!
    def delete_s3_credential(self, credential_id):
        # remove all data objects with credential
        # remove all data records with credential

        self.api.delete(credential_id)

    # FIXME: This will currently leave orphan deployments!
    def delete_swarm_credential(self, credential_id):
        # find all active deployments
        # stop all of them
        # wait for deployments to stop
        # delete credential

        self.api.delete(credential_id)

    def delete_credential(self, credential):

        credential_type = credential.get('type')
        credential_id = credential.id

        if credential_type == 'swarm':
            self.delete_swarm_credential(credential_id)
        elif credential_type == 's3':
            self.delete_s3_credential(credential_id)
        else:
            self.api.delete(credential_id)

    def delete_service(self, service_id):
        credentials = self.api.search('credential',
                                         filter='parent="{}"'.format(service_id),
                                         select='id').resources

        for credential in credentials:
            self.delete_credential(credential)

        self.api.delete(service_id)

    def delete_infra_service_group(self, nuvlabox_id):
        infra_service_groups = self.api.search('infrastructure-service-group',
                                               filter='parent="{}"'.format(nuvlabox_id),
                                               select='id').resources

        for infra_service_group in infra_service_groups:

            infra_service_group_id = infra_service_group.id

            service_hrefs = infra_service_group.data.get('infrastructure-services')
            for service_href in service_hrefs:
                service_id = service_href.get('href')
                self.delete_service(service_id)

            self.api.delete(infra_service_group_id)

    def delete_status(self, nuvlabox_id):
        entries = self.api.search('nuvlabox-status',
                                  filter='parent="{}"'.format(nuvlabox_id),
                                  select='id').resources
        for entry in entries:
            self.api.delete(entry.id)

    def delete_nuvlabox(self):
        nuvlabox_id = self.job['target-resource']['href']

        logging.info('NuvlaBox delete job started for {}.'.format(nuvlabox_id))

        nuvlabox = self.api.get(nuvlabox_id).data

        self.job.set_progress(10)

        # The state of the nuvlabox must be in 'DECOMMISSIONING' to actually try to
        # delete associated resources.  If it is not, then job should terminate correctly
        # but perform no actions.
        if nuvlabox.get('state') == 'DECOMMISSIONING':
            self.delete_status(nuvlabox_id)

            self.job.set_process(20)

            self.delete_infra_service_group(nuvlabox_id)

            self.job.set_process(30)

            self.delete_api_key(nuvlabox_id)

            self.job.set_process(40)

        return 0

    def do_work(self):
        self.delete_nuvlabox()
