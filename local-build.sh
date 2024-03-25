#!/usr/bin/env bash

IMAGE_ORG=${1:-local}
IMAGE_REPO=${2:-job}

mkdir -p $TEMP_OUTPUT_DIR || true

job_engine_version=$(poetry version -s)
IMAGE_TAG_NAME=$IMAGE_ORG/$IMAGE_REPO:$job_engine_version

echo "Building job-engine version $job_engine_version to $IMAGE_TAG_NAME"

poetry build -f wheel --no-interaction
# Export plugin will be removed from default poetry, we need to install it manually from pip
pip install poetry poetry-plugin-export

poetry export -f requirements.txt -o dist/requirements.txt --without-hashes --without-urls --with server

docker build --build-arg PACKAGE_TAG=$job_engine_version -t $IMAGE_TAG_NAME .

