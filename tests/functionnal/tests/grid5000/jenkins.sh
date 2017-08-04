#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BASE_DIR=../../../..

cd $SCRIPT_DIR

. ../utils.sh

sudo ../enos_deps.sh

sudo adduser discovery ci
sudo chown ci:ci -R $BASE_DIR
sudo chmod 774 -R $BASE_DIR
sudo rm -rf venv
sudo -u discovery ./deploy.sh
