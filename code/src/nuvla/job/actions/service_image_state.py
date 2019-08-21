# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from nuvla.connector.registry import (new_image_semantic_tag,
                                      new_image_timestamp,
                                      image_str_to_dict,
                                      image_dict_to_str,
                                      is_semantic_version)
from nuvla.connector.utils import unique_id, utc_from_now_iso
from .nuvla import Deployment, Callback, Notification
from ..actions import action


action_name = 'service_image_state'

log = logging.getLogger(action_name)

EXPIRY_FROM_NOW_SEC = 24 * 3600


@action(action_name)
class ServiceImageState(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_dpl = Deployment(self.api)

    @staticmethod
    def check_new_image(caas, sname):
        service = caas.service_get(sname)

        image = image_str_to_dict(caas.service_image_digest(service)[0])

        if is_semantic_version(image.get('tag', '')):
            return new_image_semantic_tag(image)
        else:
            s_changed_at = caas.service_get_last_timestamp(service)
            return new_image_timestamp(image, s_changed_at)

    def handle_deployment(self, deployment):
        connector = connector_factory(docker_connector, self.api, deployment.get('parent'))
        deployment_id = deployment['id']

        # FIXME: at the moment deployment UUID is the service name.
        sname = self.api_dpl.uuid(deployment)

        new_image = ServiceImageState.check_new_image(connector, sname)
        if not new_image:
            return

        # check if notification already exists
        new_image_str = image_dict_to_str(new_image)
        notif_unique_id = unique_id(deployment_id, new_image)
        notification = Notification(self.api)
        if notification.exists_with_content_unique_id(notif_unique_id):
            log.warning('Notification for {} and {} already exists. Skipping.'.format(
                deployment_id, new_image_str))
            return

        expiry = utc_from_now_iso(EXPIRY_FROM_NOW_SEC)
        acl = deployment.get('acl', None)
        msg = 'New image for deployment {0}: {1}'.format(deployment_id, new_image_str)

        callback = Callback(self.api)
        data = {'image': new_image,
                'commit': msg}
        callback_id = callback.create('deployment-update', deployment_id, data=data,
                                      expires=expiry, acl=acl)

        notification_id = notification.create(msg, 'deployment-update', notif_unique_id,
                                              expiry=expiry, target_resource=deployment_id,
                                              callback_id=callback_id, acl=acl)

        log.info('Created notification {0} with callback {1} for {2}'.format(
            notification_id, callback_id, deployment_id))

    def do_work(self):
        deployment_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(deployment_id))

        deployment = self.api_dpl.get(deployment_id)

        self.job.set_progress(10)

        try:
            self.handle_deployment(deployment)
        except Exception as ex:
            self.job.set_status_message(str(ex))
            log.error('Failed to check for new service image on {0}: {1}'.format(deployment_id, ex))
            log.exception(ex)
            return 1

        return 0
