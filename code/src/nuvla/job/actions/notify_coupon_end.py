# -*- coding: utf-8 -*-

import logging
import json
from ..actions import action

action_name = 'notify_coupon_end'

log = logging.getLogger(action_name)


@action(action_name)
class NotifyCouponEnd(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def do_work(self):
        payload = json.loads(self.job.get('payload', '{}'))
        coupon_id = payload['coupon']
        log.info(f'Job started for {action_name} for id {coupon_id}.')
        self.job.set_progress(10)
        response = self.api.hook('notify-coupon-end',
                                 {'coupon': coupon_id})
        self.job.set_status_message(response.data)

        return 0
