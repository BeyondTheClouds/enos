#!/usr/bin/env bash
# Setup of Functional Test
#    :PROPERTIES:
#    :header-args: :tangle ../../tests/functionnal/tests/tutorial/enos-node.sh :noweb yes
#    :END:

# Every source blocks of this section are going be tangled at the top of
# the functional test file.

# Set the Shebang, tells to exit immediately if a command exits with a
# non-zero status, and tells to print commands and their arguments as
# they are executed.

set -o errexit
set -o xtrace



# Then, install EnOS in your working directory (python3.5+ is required):


# enos:~/enos-myxp$
virtualenv --python=python3 venv
# (venv) enos:~/enos-myxp$
. venv/bin/activate
# (venv) enos:~/enos-myxp$
pip install "enos[openstack]==4.3.0"

# Deploy OpenStack
# EnOS manages all the aspects of an OpenStack deployment by calling
# ~enos deploy~. Concretely, the ~deploy~ phase first gets resources on
# your testbed following your configuration description. Then, it
# provisions these resources with Docker. Finally, it starts each
# OpenStack services (e.g. Keystone, Nova, Neutron) inside a dedicated
# Docker container.

# Launch the deployment with:

# (venv) enos:~/enos-myxp$
enos deploy -f reservation.yaml

# Play with OpenStack
# The last service deployed is the OpenStack dashboard (Horizon). Once
# the deployment process is finished, Horizon is reachable from G5k.
# More precisely, Horizon runs in a Docker container on the control
# node, and listens on port 80. To access Horizon from your own web
# browser (from your laptop), you can create an SSH tunnel from your
# laptop to control node, located in G5K. To that end, you first need
# to get control node’s IP address, and then create the tunnel. Open a
# new terminal and type the following:
# 1. Find the control node address using EnOS:

# (venv) enos:~/enos-myxp$
enos info
# (venv) enos:~/enos-myxp$
enos info --out json | jq -r '.rsc.control[0].address'

# Unleash the Operator in You
# OpenStack provides a command line interface to operate your Cloud. But
# before using it, you need to set your environment with the OpenStack
# credentials, so that the command line won't bother you by requiring
# credentials each time.

# Load the OpenStack credentials:

# (venv) enos:~/enos-myxp$
. current/admin-openrc



# You can then check that your environment is correctly set executing
# the following command that should output something similar to the
# listing [[lst:env-os]]:

# (venv) enos:~/enos-myxp$
env|fgrep OS_|sort



# All operations to manage OpenStack are done through one single command
# line, called ~openstack~. Doing an ~openstack --help~ displays the
# really long list of possibilities provided by this command. The
# following gives you a selection of the most often used commands to
# operate your Cloud:
# - List OpenStack running services :: ~openstack endpoint list~
# - List images :: ~openstack image list~
# - List flavors :: ~openstack flavor list~
# - List networks :: ~openstack network list~
# - List computes :: ~openstack hypervisor list~
# - List VMs (running or not) :: ~openstack server list~
# - Get details on a specific VM :: ~openstack server show <vm-name>~
# - Start a new VM :: ~openstack server create --image <image-name> --flavor <flavor-name> --nic net-id=<net-id> <vm-name>~
# - View VMs logs :: ~openstack console log show <vm-name>~

# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Functional Test Specific Code
# # We configure the VM with a keypair so that we can SSH on it without
# # being prompted by the password authentication. Otherwise the bash
# # script for the functionnal test would be stuck with `cirros@ip: `
# # waiting for the password to be given. We do not exports this part
# # into the TP, because it adds extra complexity that doesn't serve the
# # pedagogical discourse.


# (venv) enos:~/enos-myxp$
openstack keypair create --private-key ./donatello.pem donatello
# (venv) enos:~/enos-myxp$
chmod 600 ./donatello.pem
# (venv) enos:~/enos-myxp$
echo 'true' > ./test-donatello.sh



# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Based on these commands, you can use the CLI to start a new tiny
# cirros VM called ~cli-vm~:

# (venv) enos:~/enos-myxp$
openstack server create --image cirros.uec\
                        --flavor m1.tiny\
                        --network private --key-name donatello --wait\
                        cli-vm



# Then, display the information about your VM with the following command:

# (venv) enos:~/enos-myxp$
openstack server show cli-vm



# Note in particular the status of your VM. This status will go from
# ~BUILD~: OpenStack is looking for the best place to boot the VM, to
# ~ACTIVE~: your VM is running. The status could also be ~ERROR~ if you
# are experiencing hard times with your infrastructure.

# With the previous ~openstack server create~ command, the VM boots with
# a private IP. Private IPs are used for communication between VMs,
# meaning you cannot ping your VM from the lab machine. Network lovers
# will find a challenge here: try to ping the VM from the lab machine.
# For the others, you have to manually affect a floating IP to your
# machine if you want it pingable from the enos node.


# (venv) enos:~/enos-myxp$
openstack server add floating ip\
  cli-vm\
  $(openstack floating ip create public -c floating_ip_address -f value)



# You can ask for the status of your VM and its IPs with:

# (venv) enos:~/enos-myxp$
openstack server show cli-vm -c status -c addresses



# #+BEGIN_note
# Waiting for the IP to appear and then ping it could be done with a
# bunch of bash commands, such as in listing [[lst:query-ip]].

# #+CAPTION: Find the floating IP and ping it.
# #+NAME: lst:query-ip

set +o errexit
FIXED_IP=$(openstack server show cli-vm -c addresses -f value | sed  -Er 's/private=(10\.0\.0\.[0-9]+).*/\1/g')
FLOATING_IP=$(openstack floating ip list --fixed-ip-address "$FIXED_IP" -f value -c "Floating IP Address" | head -n 1)
COUNT=20
while [[ $COUNT -ne 0 ]] ; do
    ping -c 1 "$FLOATING_IP"
    RC=$?
    if [[ $RC -eq 0 ]] ; then
        COUNT=0
    else
        COUNT=$((COUNT - 1))
        sleep 5
    fi
done
set -o errexit

if [[ $RC -ne 0 ]] ; then
    echo "Timeout."; exit 124
fi



# You can also check that the VM finished to boot by looking at its logs
# with ~openstack console log show cli-vm~. The cirros VM finished to
# boot when last lines are:
# #+BEGIN_EXAMPLE
# === cirros: current=0.3.4 uptime=16.56 ===
#   ____               ____  ____
#  / __/ __ ____ ____ / __ \/ __/
# / /__ / // __// __// /_/ /\ \
# \___//_//_/  /_/   \____/___/
#    http://cirros-cloud.net


# login as 'cirros' user. default password: 'cubswin:)'. use 'sudo' for root.
# cli-vm login:
# #+END_EXAMPLE
# #+END_note

# Before going to the next section, play around with the ~openstack~ CLI
# and Horizon. For instance, list all the features offered by Nova with
# ~openstack server --help~. Here are some commands:
# 1. SSH on ~cli-vm~ using its name rather than its private IP.

# (venv) enos:~/enos-myxp$
openstack server ssh cli-vm --public --login cirros --option 'BatchMode=yes' --identity ./donatello.pem < ./test-donatello.sh


# 2. Create a snapshot of ~cli-vm~.

# (venv) enos:~/enos-myxp$
nova image-create cli-vm cli-vm-snapshot --poll


# 3. Delete the ~cli-vm~.

# (venv) enos:~/enos-myxp$
openstack server delete cli-vm --wait


# 4. Boot a new machine ~cli-vm-clone~ from the snapshot.

# (venv) enos:~/enos-myxp$
openstack server create --image cli-vm-snapshot\
                        --flavor m1.tiny\
                        --network private\
                        --wait\
                        cli-vm-clone

# Benchmark OpenStack
# Stressing a Cloud manager can be done at two levels: at the /control
# plane/ and at the /data plane/, and so it is for OpenStack. The
# control plane stresses OpenStack API. That is to say, features we used
# in the previous section to start a VM, get a floating IP, and all the
# features listed by ~openstack --help~. The data plane stresses the
# usage of resources provided by an OpenStack feature. For instance, a
# network data plane testing tool will measure how resources provided by
# Neutron handle networks communications.

# OpenStack comes with dedicated tools that provide workload to stress
# control and data plane. The one for control plane is called
# Rally[fn:rally] and the one for data plane is called
# Shaker[fn:shaker]. And these two are well integrated into EnOS.

# EnOS looks inside the ~workload~ directory for a file named ~run.yml~.


# (venv) enos:~/enos-myxp$
mkdir -p workload
# (venv) enos:~/enos-myxp$
touch workload/run.yml



# Calling Rally and Shaker from EnOS is done with:

# (venv) enos:~/enos-myxp$
enos bench --workload=workload

# Backup your results
# Rally and Shaker produce reports on executed scenarios. For instance,
# Rally produces a report with the full duration, load mean duration,
# number of iteration and percent of failures, per scenario. These
# reports, plus data measured by cAdvisor and Collectd, plus logs of
# every OpenStack services can be backup by EnOS with:

# (venv) enos:~/enos-myxp$
enos backup --backup_dir=benchresults



# The argument ~backup_dir~ tells where to store backup archives. If you
# look into this directory, you will see, among others, an archive named
# ~<controler-node>-rally.tar.gz~. Concretely, this archive contains a
# backup of Rally database with all raw data and the Rally reports. You
# can extract the Rally report of the /Nova boot and list servers/
# scenario with the following command and then open it in your favorite
# browser:

# (venv) enos:~/enos-myxp$
tar --file benchresults/*-rally.tar.gz\
    --get $(tar --file benchresults/*-rally.tar.gz\
                --list | grep "root/rally_home/report-nova-boot-list-cc.yml-.*.html")

# Bash tests                                                     :noexport:
# Reconfigure EnOS to use that new topology and check network
# constraint. I put this here rather than in the previous section
# because the syntax ~src_sh[:tangle ../../tests/functionnal/tests/tutorial/enos-node.sh]{enos deploy -f
# reservation-topo.yaml}~ doesn't work, and I have no way to write
# inline code that should be tangled.


enos deploy -f reservation-topo.yaml
enos tc
enos tc --test



# #+BEGIN_note
# If you look carefully, you will see that execution of Nova boot and
# list fails because of a SLA violation. You can try to customize
# listing [[lst:run.yml]] to make the test pass.
# #+END_note

# In this scenario Shaker launches pairs of instances on the same
# compute node. Instances are connected to different tenant networks
# connected to one router. The traffic goes from one network to the
# other (L3 east-west). Get the Shaker report with ~enos backup~ and
# analyze it. You will remark that network communications between two
# VMs co-located on the same compute are 100ms RTT. This is because
# packet are routed by Neutron service that is inside ~grp1~ and VMs are
# inside the ~grp2~.

# Now, reconfigure Neutron to use DVR[fn:dvr]. DVR will push Neutron
# agent directly on the compute of ~grp2~. With EnOS, you should do so
# by updating the ~reservation.yaml~ and add ~enable_neutron_dvr: "yes"~
# under the ~kolla~ key.

echo '  enable_neutron_dvr: "yes"' >> reservation-topo.yaml



# Then, tell EnOS to reconfigure Neutron.

# (venv) enos:~/enos-myxp$
enos os --tags=neutron --reconfigure

# Tear Down of Functional Test                                     :noexport:

# (venv) enos:~/enos-myxp$
enos destroy --hard
