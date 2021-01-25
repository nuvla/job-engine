#!/usr/bin/env python
# -*- coding: utf-8 -*-

import docker
import socket

docker_client = docker.from_env()

myself = docker_client.containers.get(socket.gethostname())

myself.pause()