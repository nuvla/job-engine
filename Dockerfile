ARG ALPINE_MAJ_MIN_VERSION=3.19
ARG PYTHON_MAJ_MIN_VERSION=3.11
ARG BASE_IMAGE=python:${PYTHON_MAJ_MIN_VERSION}-alpine${ALPINE_MAJ_MIN_VERSION}
ARG DOCKER_VERSION=25-cli

FROM docker:${DOCKER_VERSION} AS docker
FROM ${BASE_IMAGE}

ARG KUBECTL_VERSION=1.32
ARG HELM_VERSION=3.14
ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG IMAGE_NAME
ARG PACKAGE_TAG=3.9.4

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}

# Docker and docker compose CLIs
COPY --from=docker /usr/local/bin/docker /usr/bin/docker
#COPY --from=docker /usr/local/libexec/docker/cli-plugins/docker-compose \
#                   /usr/local/libexec/docker/cli-plugins/docker-compose

# Need scp (openssh) for docker-machine to transfer files to machines.
RUN apk --no-cache add gettext bash openssl openssh curl ca-certificates \
    "helm~${HELM_VERSION}"
RUN apk --no-cache add --repository https://dl-cdn.alpinelinux.org/alpine/edge/community \
    "kubectl~${KUBECTL_VERSION}"

# Docker Compose
RUN set -eux; \
    apkArch="$(apk --print-arch)"; \
    curl -L -o /usr/local/libexec/docker/cli-plugins/docker-compose --create-dirs \
         https://github.com/SixSq/docker-compose/releases/download/v2.29.0-sixsq/docker-compose-linux-${apkArch} && \
    chmod +x /usr/local/libexec/docker/cli-plugins/docker-compose


COPY --link dist/requirements.txt /tmp/build/requirements.txt
RUN pip install -r /tmp/build/requirements.txt

COPY --link dist/nuvla_job_engine-${PACKAGE_TAG}-py3-none-any.whl /tmp/build/nuvla_job_engine-${PACKAGE_TAG}-py3-none-any.whl
RUN pip install /tmp/build/nuvla_job_engine-${PACKAGE_TAG}-py3-none-any.whl

RUN cp -r /usr/local/lib/python3.11/site-packages/nuvla/scripts/ /app/
RUN chmod -R +x /app/

RUN rm -rf /tmp/build/

# inherited from docker:18.09 Dockerfile
RUN [ ! -e /etc/nsswitch.conf ] && echo 'hosts: files dns' > /etc/nsswitch.conf || true

ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"
ENV IMAGE_NAME=${IMAGE_NAME}

ADD https://raw.githubusercontent.com/docker-library/docker/master/modprobe.sh /usr/local/bin/modprobe

# my_init as ENTRYPOINT to protect us from zombies.
# It assumes python3 at that location.
RUN ln -s $(which python3) /usr/bin/python3
RUN curl --proto "=https" -fsSL -o /app/my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 /app/my_init
RUN ln -s /app/my_init /usr/bin/my_init

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["my_init"]
