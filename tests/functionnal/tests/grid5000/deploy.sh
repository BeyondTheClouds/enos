#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR=../../../..

cd $SCRIPT_DIR

. ../utils.sh

virtualenv venv
. venv/bin/activate

pip install -e $BASE_DIR

echo "-ENOS DEPLOY-"
enos deploy -f grid5000.yaml
sanity_check
echo "-ENOS DESTROY-"
enos destroy

# Clean everything
echo "-ENOS DESTROY HARD-"
enos destroy --hard
