FROM python:3.11-alpine3.18

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG GITHUB_RUN_ID
ARG IMAGE_NAME

ARG DOCKER_CLIENT_VERSION=23.0
ARG DOCKER_COMPOSE_VERSION=2.17
ARG KUBECTL_VERSION=1.27
ARG HELM_VERSION=3.11

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}
LABEL ci.build.number=${GITHUB_RUN_ID}

COPY --from=docker/compose:alpine-1.29.2 /usr/local/bin/docker-compose /usr/local/bin/

RUN apk --no-cache add gettext \
    "docker-cli~${DOCKER_CLIENT_VERSION}" \
    "docker-cli-compose~${DOCKER_COMPOSE_VERSION}"
RUN apk --no-cache add --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    "kubectl~${KUBECTL_VERSION}"

ADD target/job /target/job

RUN mv /target/job/requirements.lite.txt /target/job/requirements.txt && \
    pip install --no-cache-dir /target/job && \
    mv /target/job/src/scripts/ /app/ && \
    chmod -R +x /app/ && \
    rm -rf /target/

ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"
ENV IMAGE_NAME ${IMAGE_NAME}

# my_init as ENTRYPOINT to protect us from zombies.
# It assumes python3 at that location.
RUN ln -s $(which python3) /usr/bin/python3

WORKDIR /app

RUN wget -O my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 my_init

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["/app/my_init"]
