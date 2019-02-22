FROM python:3-alpine

ADD target/job /app/job
ADD target/python-library /app/python-library

RUN pip install /app/python-library && \
        pip install /app/job && \
        chmod -R +x /app/job/src/scripts/

# inherited from docker:18.09 Dockerfile
RUN apk add --no-cache ca-certificates curl
RUN [ ! -e /etc/nsswitch.conf ] && echo 'hosts: files dns' > /etc/nsswitch.conf

ENV DOCKER_CHANNEL stable
ENV DOCKER_VERSION 18.09.2

RUN set -eux; \
	\
	apkArch="$(apk --print-arch)"; \
	case "$apkArch" in \
		x86_64) dockerArch='x86_64' ;; \
		armhf) dockerArch='armel' ;; \
		aarch64) dockerArch='aarch64' ;; \
		ppc64le) dockerArch='ppc64le' ;; \
		s390x) dockerArch='s390x' ;; \
		*) echo >&2 "error: unsupported architecture ($apkArch)"; exit 1 ;;\
	esac; \
	\
	if ! wget -O docker.tgz "https://download.docker.com/linux/static/${DOCKER_CHANNEL}/${dockerArch}/docker-${DOCKER_VERSION}.tgz"; then \
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

ADD https://raw.githubusercontent.com/docker-library/docker/65fab2cd767c10f22ee66afa919eda80dbdc8872/18.09/modprobe.sh /usr/local/bin/modprobe

RUN curl -L https://github.com/docker/machine/releases/download/v0.16.0/docker-machine-$(uname -s)-$(uname -m) >/tmp/docker-machine && \
            install /tmp/docker-machine /usr/local/bin/docker-machine &&\
            pip install python-docker-machine

ENTRYPOINT ["/app/job/src/scripts/job_executor.py"]
