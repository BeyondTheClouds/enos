#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

cd $SCRIPT_DIR

sudo ../enos_deps.sh

virtualenv venv
. venv/bin/activate

pip install -e ../../../..

enos deploy -f grid5000.yaml &&\
enos destroy

# Clean everything
enos destroy --hard
