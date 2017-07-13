#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# common steps
$SCRIPT_DIR/../vagrant_deps.sh
$SCRIPT_DIR/../enos_deps.sh

cd $SCRIPT_DIR

virtualenv venv
. venv/bin/activate

pip install -e ../../../..

enos deploy -f vbox.yaml && enos destroy
