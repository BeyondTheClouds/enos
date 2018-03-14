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

# removing previously installed images
command -v docker && (sudo docker ps -q | xargs sudo docker rm -f)
command -v docker && (sudo docker images -q | xargs sudo docker rmi)

sudo -u discovery ./deploy.sh

# stopping some containers
command -v docker && ( sudo docker ps -q | xargs sudo docker stop)

# saving the env
sudo tgz-g5k > /tmp/enos.tgz
