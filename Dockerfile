FROM python:3.11-alpine3.18

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG IMAGE_NAME

ARG DOCKER_CLIENT_VERSION=25.0
ARG DOCKER_COMPOSE_VERSION=2.17
ARG KUBECTL_VERSION=1.29
ARG HELM_VERSION=3.11

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}
LABEL ci.build.number=${TRAVIS_BUILD_NUMBER}
LABEL ci.build.web.url=${TRAVIS_BUILD_WEB_URL}

# Need scp (openssh) for docker-machine to transfer files to machines.
RUN apk --no-cache add gettext bash openssl openssh \
    "helm~${HELM_VERSION}" \
    "docker-cli~${DOCKER_CLIENT_VERSION}" \
    "docker-cli-compose~${DOCKER_COMPOSE_VERSION}"
RUN apk --no-cache add --repository https://dl-cdn.alpinelinux.org/alpine/edge/community \
    "kubectl~${KUBECTL_VERSION}"

COPY --link dist/scripts/ /app
RUN chmod -R +x /app/

COPY --link dist/requirements.txt /tmp/build/requirements.txt
RUN pip install -r /tmp/build/requirements.txt

COPY --link dist/nuvla_job_engine-3.9.4-py3-none-any.whl /tmp/build/nuvla_job_engine-3.9.4-py3-none-any.whl
RUN pip install /tmp/build/nuvla_job_engine-3.9.4-py3-none-any.whl

RUN rm -rf /tmp/build/

# inherited from docker:18.09 Dockerfile
RUN apk add --no-cache ca-certificates curl
RUN [ ! -e /etc/nsswitch.conf ] && echo 'hosts: files dns' > /etc/nsswitch.conf || true

ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"
ENV IMAGE_NAME ${IMAGE_NAME}

ADD https://raw.githubusercontent.com/docker-library/docker/master/modprobe.sh /usr/local/bin/modprobe

# This only works for amd64 but it also isn't necessary for push mode
# since its only use is for infrastructure_service_swarm_start/stop, and that's a server-side feature
RUN curl --proto "=https" -s -L https://github.com/docker/machine/releases/download/v0.16.2/docker-machine-$(uname -s)-$(uname -m) >/tmp/docker-machine && \
            install /tmp/docker-machine /usr/local/bin/docker-machine && rm -f /tmp/docker-machine

# my_init as ENTRYPOINT to protect us from zombies.
# It assumes python3 at that location.
RUN ln -s $(which python3) /usr/bin/python3
RUN curl --proto "=https" -fsSL -o /app/my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 /app/my_init
RUN ln -s /app/my_init /usr/bin/my_init

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["my_init"]
