#!/usr/bin/env bash
set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

cd $SCRIPT_DIR

sudo ../enos_deps.sh
sudo ../vagrant_deps.sh

virtualenv venv
. venv/bin/activate
pip install -U pip
pip install -e ../../../..

enos up -f topology.yaml &&\
enos info &&\
enos tc &&\
enos tc --test

# TODO: get the results and check their correctness
cat current/*.out &&\
cat current/*.stats
