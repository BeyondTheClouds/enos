#!/usr/bin/env bash

function sanity_check {
echo "-SANITY CHECK-"
BASE_DIR=$1

# shellcheck disable=SC1091
. current/admin-openrc
# The openstack client aren't pulled by EnOS anymore.
# A good practice is to use them inside the generated venv_kolla even if that's
# possible to use them from the main venv

. venv_kolla/bin/activate

pip install python-openstackclient \
    python-neutronclient \
    python-glanceclient

echo "-OPENSTACK VALIDATION-"
sleep 15
openstack endpoint list
openstack image list
openstack flavor list
nova --debug service-list
neutron --debug agent-list
nova\
  --debug\
  boot\
  --poll\
  --image cirros.uec\
  --flavor m1.tiny\
  --nic net-id="$(openstack network show private --column id --format value)"\
  jenkins-vm
nova delete jenkins-vm

echo "-ENOS BENCH-"
enos bench --workload="$BASE_DIR/enos/workload"

echo "-ENOS BACKUP-"
enos backup

echo "-/SANITY CHECK-"
}
