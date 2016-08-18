#! /bin/bash

#kolla/tools/kolla-ansible prechecks -i current/multinode --configdir current

#kolla/tools/kolla-ansible pull -i current/multinode --configdir current

kolla/tools/kolla-ansible deploy -i current/multinode --configdir current
