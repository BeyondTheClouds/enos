#!/usr/bin/env bash

set -xe

apt-get -y update
# install vagrant
wget https://releases.hashicorp.com/vagrant/2.0.3/vagrant_2.0.3_x86_64.deb -O vagrant.deb
dpkg -i vagrant.deb
apt-get -f -y  install
# install vbox
wget https://download.virtualbox.org/virtualbox/5.2.8/virtualbox-5.2_5.2.8-121009~Debian~jessie_amd64.deb -O vbox.deb
dpkg -i vbox.deb || true
apt-get -f -y  install

# Get rid of size limitations on g5K
#dir=".vagrant.d"
#mkdir -p "/tmp/$dir"
#mkdir -p "/root/$dir"
#mount -o bind "/tmp/$dir" "/root/$dir"
#dir="VirtualBox VMs"
#mkdir -p "/tmp/$dir"
#mkdir -p "/root/$dir"
#mount -o bind "/tmp/$dir" "/root/$dir"


