#!/bin/sh -x
# NOTE(msimonin): -u won't work as _OLD_PYTHON_PATH is unset
# when calling the first time activate

# This script is called inside the virtual machine
BUILD_DIR=$HOME/enos_sources
TEST_DIR=$BUILD_DIR/tests/functionnal/vagrant/packaging

# Making the switch to enos venv when login
cat << EOF >> ~/.profile
. /home/vagrant/enos_sources/venv/bin/activate
EOF

cd $TEST_DIR
virtualenv venv
. venv/bin/activate

pip install -e $BUILD_DIR

enos deploy -f reservation.yaml && enos destroy

# some cleaning
sudo rm -rf enos_*
sudo rm -rf /root/rally_home
sudo rm -rf /root/shaker_home

