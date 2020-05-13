#!/bin/bash -xe

MANIFEST=${DOCKER_ORG}/${DOCKER_IMAGE}:${DOCKER_TAG}

platforms=(amd64 arm64 arm)
manifest_args=(${MANIFEST})

#
# login to docker hub
#

unset HISTFILE
echo ${DOCKER_PASSWORD} | docker login -u ${DOCKER_USERNAME} --password-stdin

#
# push all generated images
#

for platform in "${platforms[@]}"; do
    docker push ${MANIFEST}-${platform}
    manifest_args+=("${MANIFEST}-${platform}")    
done

#
# create manifest, update, and push
#

export DOCKER_CLI_EXPERIMENTAL=enabled
docker manifest create "${manifest_args[@]}"

for platform in "${platforms[@]}"; do
    docker manifest annotate ${MANIFEST} ${MANIFEST}-${platform} --arch ${platform}
done

docker manifest push --purge ${MANIFEST}
