FROM python:3.8-alpine3.12

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

COPY --from=nuvladev/job-docker-compose-client:master /usr/local/bin/docker-compose /usr/local/bin/
COPY --from=nuvladev/job-docker-compose-client:master /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages

ADD target/job /target/job

RUN mv /target/job/requirements.lite.txt /target/job/requirements.txt && \
    pip install /target/job && \
    mv /target/job/src/scripts/ /app/ && \
    chmod -R +x /app/ && \
    rm -rf /target/

# inherited from docker:18.09 Dockerfile
RUN [ ! -e /etc/nsswitch.conf ] && echo 'hosts: files dns' > /etc/nsswitch.conf

ENV DOCKER_CHANNEL stable
ENV DOCKER_VERSION 19.03.5
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
		--file docker.tgz docker/docker \
		--strip-components 1 \
		--directory /usr/local/bin/ \
	; \
	rm docker.tgz; \
	\
	docker --version

ADD https://raw.githubusercontent.com/docker-library/docker/65fab2cd767c10f22ee66afa919eda80dbdc8872/18.09/modprobe.sh /usr/local/bin/modprobe

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
      k8s_release=$(python3 -c 'import requests;print(requests.get("https://storage.googleapis.com/kubernetes-release/release/stable.txt").text)'); \
    	wget https://storage.googleapis.com/kubernetes-release/release/${k8s_release}/bin/linux/${kubectlArch}/kubectl && \
    	chmod +x ./kubectl && \
    	mv ./kubectl /usr/local/bin/kubectl && \
    	timeout 5s kubectl version --client=true || echo "WARNING: kubectl failed to get version. Continuing anyway"

RUN apk --no-cache add gettext

# my_init as ENTRYPOINT to protect us from zombies.
# It assumes python3 at that location.
RUN ln -s $(which python3) /usr/bin/python3

WORKDIR /app

RUN wget -O my_init https://raw.githubusercontent.com/phusion/baseimage-docker/rel-0.9.19/image/bin/my_init && \
    chmod 700 my_init

# Start your app by "-- /my/app --foo bar --baz"
ENTRYPOINT ["/app/my_init"]
