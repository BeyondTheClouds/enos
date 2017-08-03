#!/bin/bash -eux
BUILD_DIR=$HOME/enos

cd $BUILD_DIR
tar -xvf enos.tar
chown vagrant:vagrant -R *
