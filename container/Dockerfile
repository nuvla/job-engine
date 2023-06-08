FROM python:3.11-alpine3.18

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG TRAVIS_BUILD_NUMBER
ARG TRAVIS_BUILD_WEB_URL
ARG IMAGE_NAME

ARG DOCKER_CLIENT_VERSION=23.0
ARG DOCKER_COMPOSE_VERSION=2.17
ARG KUBECTL_VERSION=1.27
ARG HELM_VERSION=3.11

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}
LABEL ci.build.number=${TRAVIS_BUILD_NUMBER}
LABEL ci.build.web.url=${TRAVIS_BUILD_WEB_URL}

COPY --from=docker/compose:alpine-1.29.2 /usr/local/bin/docker-compose /usr/local/bin/

# Need scp (openssh) for docker-machine to transfer files to machines.
RUN apk --no-cache add gettext bash openssl openssh \
    "helm~${HELM_VERSION}" \
    "docker-cli~${DOCKER_CLIENT_VERSION}" \
    "docker-cli-compose~${DOCKER_COMPOSE_VERSION}"
RUN apk --no-cache add --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    "kubectl~${KUBECTL_VERSION}"

ADD target/job /target/job

RUN pip install --no-cache-dir /target/job && \
    mv /target/job/src/scripts/ /app/ && \
    chmod -R +x /app/ && \
    rm -rf /target/

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

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["/app/my_init"]
