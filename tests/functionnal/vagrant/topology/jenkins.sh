#!/usr/bin/env bash
set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# common steps
$SCRIPT_DIR/../enos_deps.sh
$SCRIPT_DIR/../vagrant_deps.sh

cd $SCRIPT_DIR

virtualenv venv
. venv/bin/activate
pip install -e ../../../..

enos up -f topology.yaml &&\
enos info &&\
enos tc &&\
enos tc --test

# TODO: get the results and check their correctness
cat current/*.out &&\
cat current/*.stats
