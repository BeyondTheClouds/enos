#!/bin/bash
set -x
sudo ip link show veth0 || sudo ip link add type veth peer
echo "veth0 mounted through userdata script" > /tmp/userdata.log
