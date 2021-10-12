FROM python:3.10-alpine

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG TRAVIS_BUILD_NUMBER
ARG TRAVIS_BUILD_WEB_URL
ARG IMAGE_NAME

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}
LABEL ci.build.number=${TRAVIS_BUILD_NUMBER}
LABEL ci.build.web.url=${TRAVIS_BUILD_WEB_URL}

COPY --from=docker/compose:alpine-1.26.2 /usr/local/bin/docker-compose /usr/local/bin/

ADD target/job /target/job

RUN pip install /target/job && \
    mv /target/job/src/scripts/ /app/ && \
    chmod -R +x /app/ && \
    rm -rf /target/

# inherited from docker:18.09 Dockerfile
RUN apk add --no-cache ca-certificates curl
RUN [ ! -e /etc/nsswitch.conf ] && echo 'hosts: files dns' > /etc/nsswitch.conf

ENV DOCKER_CHANNEL stable
ENV DOCKER_VERSION 20.10.7
ENV PYTHONWARNINGS "ignore:Unverified HTTPS request"
ENV IMAGE_NAME ${IMAGE_NAME}

RUN set -eux; \
	\
	apkArch="$(apk --print-arch)"; \
	case "$apkArch" in \
		x86_64) dockerArch='x86_64' ;; \
		armhf) dockerArch='armel' ;; \
		armv7) dockerArch='armhf' ;; \
		aarch64) dockerArch='aarch64' ;; \
		ppc64le) dockerArch='ppc64le' ;; \
		s390x) dockerArch='s390x' ;; \
		*) echo >&2 "error: unsupported architecture ($apkArch)"; exit 1 ;;\
	esac; \
	\
	if ! wget -q -O docker.tgz "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/${dockerArch}/docker-${DOCKER_VERSION}.tgz"; then \
		echo >&2 "error: failed to download 'docker-${DOCKER_VERSION}' from '${DOCKER_CHANNEL}' for '${dockerArch}'"; \
		exit 1; \
	fi; \
	\
	tar --extract \
		--file docker.tgz \
		--strip-components 1 \
		--directory /usr/local/bin/ \
	; \
	rm docker.tgz; \
	\
	dockerd --version; \
	docker --version

ADD https://raw.githubusercontent.com/docker-library/docker/master/20.10/modprobe.sh /usr/local/bin/modprobe

# This only works for amd64 but it also isn't necessary for push mode
# since its only use is for infrastructure_service_swarm_start/stop, and that's a server-side feature
RUN curl -s -L https://github.com/docker/machine/releases/download/v0.16.2/docker-machine-$(uname -s)-$(uname -m) >/tmp/docker-machine && \
            install /tmp/docker-machine /usr/local/bin/docker-machine && rm -f /tmp/docker-machine
# Need scp for docker-machine to transfer files to machines.
RUN apk add --no-cache openssh

RUN set -eux; \
    	\
    	apkArch="$(apk --print-arch)"; \
    	case "$apkArch" in \
    		x86_64) kubectlArch='amd64' ;; \
    		armv7) kubectlArch='arm' ;; \
        aarch64) kubectlArch='amd64' ;; \
    		*) echo >&2 "error: unsupported architecture ($apkArch) for kubectl"; exit 1 ;;\
    	esac; \
    	\
    	curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/${kubectlArch}/kubectl && \
    	chmod +x ./kubectl && \
    	mv ./kubectl /usr/local/bin/kubectl && \
    	kubectl version --client=true

RUN apk --no-cache add gettext

RUN apk add --no-cache bash openssl
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh && \
    rm -f ./get_helm.sh

# my_init as ENTRYPOINT to protect us from zombies.
# It assumes python3 at that location.
RUN ln -s $(which python3) /usr/bin/python3
RUN curl -fsSL -o /app/my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 /app/my_init

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["/app/my_init"]
