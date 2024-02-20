# -*- coding: utf-8 -*-

import logging

from ...connector.registry import (new_image_semantic_tag,
                                   image_dict_to_str,
                                   is_semantic_version)
from ...connector.utils import (unique_id,
                                utc_from_now_iso)
from nuvla.api.resources import Module, Callback, Notification
from ..actions import action

action_name = 'component_image_state'

log = logging.getLogger(action_name)

EXPIRY_FROM_NOW_SEC = 24 * 3600


@action(action_name)
class ComponentImageState(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api
        self.api_module = Module(self.api)

    @staticmethod
    def check_new_image(image):
        if is_semantic_version(image.get('tag', '')):
            return new_image_semantic_tag(image)
        else:
            return None

    def handle_component(self, component):
        new_image = ComponentImageState.check_new_image(component['content']['image'])
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

        expiry = utc_from_now_iso(EXPIRY_FROM_NOW_SEC)
        acl = component.get('acl', None)
        msg = 'New image for component {0}: {1}\nUUID: {2}'.format(
            component.get('path', ''), new_image_str, component_id)

        content = component['content']
        content.update({'image': new_image, 'commit': msg})

        callback = Callback(self.api)
        callback_id = callback.create('module-update', component_id, data=content,
                                      expires=expiry, acl=acl)

        notification_id = notification.create(msg, 'module-update', notif_unique_id,
                                              expiry=expiry, target_resource=component_id,
                                              callback_id=callback_id, acl=acl)

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
