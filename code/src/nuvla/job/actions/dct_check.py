# -*- coding: utf-8 -*-

import json
import yaml
import logging

from subprocess import run
from collections.abc import Iterable
from ..actions import action

action_name = 'dct_check'

log = logging.getLogger(action_name)

def iterable(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes, bytearray))

def find_in_dict(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            yield obj[key]
        for k, v in obj.items():
            if iterable(v):
                for i in find_in_dict(v, key):
                    yield i
    elif iterable(obj):
        for o in obj:
            for i in find_in_dict(o, key):
                yield i


@action(action_name)
class DockerContentTrustCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def get_images(self, href):
        element = self.api.get(href).data
        if href.startswith('module/'):
            module = element
        else:
            module = element['module']
        subtype = module['subtype']
        images  = []

        if subtype == 'component':
            image = module['content']['image']
            image_name = ''
            if image.get('registry'):
                image_name += '{}/'.format(image['registry'])
            if image.get('repository'):
                image_name += '{}/'.format(image['repository'])
            image_name += image['image-name']
            if image.get('tag'):
                image_name += ':{}'.format(image['tag'])
            images = [image_name]
        elif subtype in ['application', 'application_kubernetes']:
            docker_compose = module['content']['docker-compose']
            compose_file = list(yaml.load_all(docker_compose, Loader=yaml.FullLoader))
            images = find_in_dict(compose_file, 'image')
        else:
            status_message = 'Unsupported module type: {}'.format(subtype)
            log.error(status_message)
            self.job.set_status_message(status_message)
            raise Exception(status_message)
        return images

    def verify_images(self, images):
        return {i: self.docker_trust_inspect(i) for i in images}

    def docker_trust_inspect(self, image):
        if ':' not in image:
            image += ':latest'
        result = run(['docker', 'trust', 'inspect', image])
        return result.returncode == 0

    def do_work(self):
        action_name = self.job['action']
        href = self.job['target-resource']['href']

        log.info('Job {} started for {}.'.format(action_name, href))

        try:
            self.job.set_progress(10)
            images = set(self.get_images(href))
            self.job.set_progress(50)
            images_status = self.verify_images(images)
            self.job.set_progress(90)
            print(images_status)
            self.job.set_status_message(json.dumps(images_status))
        except Exception as ex:
            log.error('Failed to {} {}: {}'.format(action_name, href, ex))
            self.job.set_status_message(str(ex).splitlines()[-1])
            return 1

        return 0
