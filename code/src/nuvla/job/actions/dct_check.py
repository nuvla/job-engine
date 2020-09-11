# -*- coding: utf-8 -*-

import json
import yaml
import logging

from subprocess import run

from ..actions import action

action_name = 'dct_check'

log = logging.getLogger(action_name)


def find_in_dict(d, key):
    if key in d:
        yield d[key]
    for k, v in d.items():
        if isinstance(v, dict):
            for i in find_in_dict(v, key):
                yield i


@action(action_name)
class DockerContentTrustCheck(object):

    def __init__(self, _, job):
        self.job = job
        self.api = job.api

    def get_images(self, deployment_id):
        deployment = self.api.get(deployment_id).data
        module  = deployment['module']
        subtype = module['subtype']
        images  = []

        if subtype == "component":
            image = module['content']['image']
            image_name = '{repository}/{image-name}:{tag}'.format(**image)
            images = [image_name]
        elif subtype == "application":
            docker_compose = module['content']['docker-compose']
            compose_file = yaml.load(docker_compose, Loader=yaml.FullLoader)
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
        result = run(['docker', 'trust', 'inspect', image])
        return result.returncode == 0

    def do_work(self):
        action_name   = self.job['action']
        deployment_id = self.job['target-resource']['href']

        log.info('Job {} started for {}.'.format(action_name, deployment_id))

        try:
            self.job.set_progress(10)
            images = set(self.get_images(deployment_id))
            self.job.set_progress(50)
            images_status = self.verify_images(images)
            self.job.set_progress(90)
            print(images_status)
            self.job.set_status_message(json.dumps(images_status))
        except Exception as ex:
            log.error('Failed to {} {}: {}'.format(action_name, infra_service_id, ex))
            self.job.set_status_message(str(ex).splitlines()[-1])
            return 1

        return 0
