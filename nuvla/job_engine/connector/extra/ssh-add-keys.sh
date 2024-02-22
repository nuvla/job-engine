#!/bin/bash
set -e
mkdir -p ~/.ssh
cat $1 >> ~/.ssh/authorized_keys
