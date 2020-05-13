#!/bin/bash -xe

MANIFEST=${DOCKER_ORG}/${DOCKER_IMAGE}:${DOCKER_TAG}

platforms=(amd64 arm64 arm)

#
# remove any previous builds
#

rm -Rf target/*.tar
mkdir -p target

#
# generate image for each platform
#

for platform in "${platforms[@]}"; do 
    docker run --rm --privileged -v ${PWD}:/tmp/work --entrypoint buildctl-daemonless.sh moby/buildkit:master \
           build \
           --frontend dockerfile.v0 \
           --opt platform=linux/${platform} \
           --opt filename=./Dockerfile \
           --opt build-arg:GIT_BRANCH=${GIT_BRANCH} \
           --opt build-arg:GIT_BUILD_TIME=${GIT_BUILD_TIME} \
           --opt build-arg:GIT_COMMIT_ID=${GIT_COMMIT_ID} \
           --opt build-arg:GIT_DIRTY=${GIT_DIRTY} \
           --opt build-arg:TRAVIS_BUILD_NUMBER=${TRAVIS_BUILD_NUMBER} \
           --opt build-arg:TRAVIS_BUILD_WEB_URL=${TRAVIS_BUILD_WEB_URL} \
           --output type=docker,name=${MANIFEST}-${platform},dest=/tmp/work/target/${DOCKER_IMAGE}-${platform}.docker.tar \
           --local context=/tmp/work \
           --local dockerfile=/tmp/work \
           --progress plain

done

#
# load all generated images
#

for platform in "${platforms[@]}"; do
    docker load --input ./target/${DOCKER_IMAGE}-${platform}.docker.tar
done

