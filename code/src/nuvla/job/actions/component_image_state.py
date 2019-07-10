# -*- coding: utf-8 -*-

import logging

from nuvla.connector import connector_factory, docker_connector
from nuvla.connector.registry import (new_image_semantic_tag,
                                      new_image_timestamp,
                                      image_dict_to_str,
                                      is_semantic_version)
from nuvla.connector.utils import (unique_id,
                                   utc_from_now_iso,
                                   timestr2dtime)
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

    def check_new_image(self, image, c_changed_at):

        if is_semantic_version(image.get('tag')):
            return new_image_semantic_tag(image)
        else:
            return new_image_timestamp(image, timestr2dtime(c_changed_at))

    def handle_component(self, component):
        new_image = self.check_new_image(component['content']['image'],
                                         component['content']['updated'])
        if not new_image:
            return

        component_id = component['id']

        # check if notification already exists
        new_image_str = image_dict_to_str(new_image)
        notif_unique_id = unique_id(component_id, new_image)
        notification = Notification(self.api)
        if notification.exists_with_content_unique_id(notif_unique_id):
            log.warning('Notification for {} and {} already exists. Skipping.'.format(
                component_id, new_image_str))
            return

        expires = utc_from_now_iso(EXPIRY_FROM_NOW_SEC)

        callback = Callback(self.api)
        data = {'content':
                    {'image': new_image}}
        callback_id = callback.create('component-update', component_id, data=data, expires=expires)

        msg = 'Newer image available for component {0}: {1}'.format(
            component_id, new_image_str)
        notification_id = notification.create(msg, action_name, notif_unique_id,
                                              expires=expires, target_resource=component_id, callback_id=callback_id)

        log.info('Created notification {0} with callback {1} for {2}'.format(
            notification_id, callback_id, component_id))

    def do_work(self):
        component_id = self.job['target-resource']['href']

        log.info('Job started for {}.'.format(component_id))

        component = self.api_module.get(component_id)

        self.job.set_progress(10)

        try:
            self.handle_component(component)
        except Exception as ex:
            self.job.set_status_message(str(ex))
            log.error('Failed to obtain component image state {0}: {1}'.format(component_id, ex))
            log.exception(ex)
            return 1

        return 0
