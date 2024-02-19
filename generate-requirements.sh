#!/usr/bin/env bash

OUTPUT_DIR=${1:-.}

mkdir -p $OUTPUT_DIR || true

echo $OUTPUT_DIR

poetry export \
  -f requirements.txt \
  -o $OUTPUT_DIR/requirements.txt \
  --without-hashes \
  --without-urls \
  --with server

poetry export \
  -f requirements.txt \
  -o $OUTPUT_DIR/requirements.test.txt \
  --without-hashes \
  --without-urls \
  --with test \
  --with server

poetry export \
  -f requirements.txt \
  -o $OUTPUT_DIR/requirements.lite.txt \
  --without-hashes \
  --without-urls
