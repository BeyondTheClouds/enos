#!/bin/bash -ex

# NOTE(msimonin): -u won't work as _OLD_PYTHON_PATH is unset
# when calling the first time activate

# This script is called inside the virtual machine
BASE_DIR=$HOME/enos_sources
TEST_DIR=$BASE_DIR/tests/functionnal/tests/packaging

cd "$TEST_DIR"
# shellcheck disable=SC1091
. ../utils.sh

virtualenv venv
# shellcheck disable=SC1091
. venv/bin/activate

# Making the switch to enos venv when login
cat << EOF >> ~/.profile
. $TEST_DIR/venv/bin/activate
EOF

pip install -e "$BASE_DIR"
pip install git+https://github.com/beyondtheclouds/enoslib

enos deploy -f reservation.yaml
sanity_check "$BASE_DIR"
enos destroy

# some cleaning
sudo rm -rf "$BASE_DIR"/enos_*
sudo rm -rf "$BASE_DIR"/current
sudo rm -rf /root/rally_home
sudo rm -rf /root/shaker_home

