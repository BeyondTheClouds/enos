#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

cd $SCRIPT_DIR

sudo ../vagrant_deps.sh
sudo ../enos_deps.sh

virtualenv venv
. venv/bin/activate

pip install -e ../../../..

# some cleaning
vagrant destroy -f || true
enos deploy -f vbox.yaml && enos destroy
