=================================
EnOS Tutorial on top of Grid’5000
=================================


OpenStack [1]_  has become the *defacto* solution to operate
compute, network and storage resources in public and private Clouds.
This lab aims at exploring EnOS [2]_  [3]_ , a
holistic framework to conduct evaluations of different OpenStack
configurations in an easy and reproducible manner. In particular, EnOS
helps you in deploying real OpenStack instances on different types of
infrastructure (from virtual environments based on VMs like Vagrant,
to real large-scale testbeds composed of bare-metal machines like
Grid’5000), stressing it and getting feedback. This lab is composed of
two part:

The first part is about getting started with EnOS. More precisely we
are going to:

- Deploy and configure OpenStack on Grid’5000 using EnOS.

- Operate this OpenStack to manage IaaS resources (*e.g.*, boot VMs).

- Understand the benchmark mechanisms and run some evaluations.

- Visualize the collected metrics through Grafana.

For those who desire to go further, we propose to use EnOS to
investigate OpenStack in WAN networks. In this investigation we will
study the impact of a specific feature used in such context, just like
a developer would do. To that end, we will:

- Simulate a WAN-wide topology with EnOS by playing with traffic
  shaping.

- See how EnOS can be used to customize OpenStack (enable/disable
  features).

- Benchmark the deployed OpenStack and backup metrics.

- Analyze the collected metrics to highlight the impact of features.

1 Requirements and Setup
------------------------

To follow the lab you’ll need :

- A Web browser (*e.g.*, Firefox)

- A Grid’5000 account

- An SSH client (*e.g.*, OpenSSH on Linux/Mac, Putty on Windows)

  - Follow the `G5K’s recommendations <https://www.grid5000.fr/mediawiki/index.php/SSH#Setting_up_a_user_config_file>`_ and edit your ``~/.ssh/config``
    file to configure SSH for Grid’5000.

  - Be sure your configure works by typing ``ssh rennes.g5k`` for
    instance.

2 Presentation
--------------

.. note::

    Since OpenStack deployment can be quite long (~20, 30 minutes) you
    might be interested in starting its deployment before reading the
    presentation of OpenStack and EnOS (you can `4 Deploy OpenStack using EnOS`_ and come
    back later).

Adrien Lebre gave a lecture regarding Cloud Computing, OpenStack and
EnOS. You can find the slides of this lecture `here <http://enos.irisa.fr/tp-polytech/openstack-slides.pdf>`_. In the following,
we quickly present some information regarding OpenStack, EnOS and the
lab we are going to set today.

2.1 OpenStack
~~~~~~~~~~~~~

OpenStack is the *defacto* solution to manage infrastructures
(*i.e.*, compute, network, storage resources). To that end, it
provides management mechanisms as a modular platform composed of
several projects, each of which is in charge of an aspect of the
infrastructure management. Among the various projects (30+), here is a
selection corresponding to the bare necessities to operate
infrastructure:

Nova    
    the compute resource manager (*i.e.*,
    virtual/bare-metal machines and containers)

Glance  
    the image store

Neutron 
    the network manager for compute resources
    interconnection

Keystone
    the authentication/authorization manager

Each project are themselves based on multiple modules. Since OpenStack
is designed as a distributed software, each module can be deployed on
different physical/virtual machines. For instance, here is a set of
modules that compose Nova:

- ``nova-api``: in charge of managing users’ requests

- ``nova-scheduler``: in charge of scheduling compute resources on
  compute nodes

- ``nova-compute``: in charge of the life-cycle of compute resources

- ...

To provide all the features expected by an infrastructure manager,
OpenStack’s modules need cooperation. For instance, when a user asks
nova to boot a VM, the image is fetched from glance, its network
interfaces are configured by neutron, supposing keystone authorized
the operation. Such cooperation is possible through three
communication channels:

REST APIs               
    used for inter-project communications

Message queue (RabbitMQ)
    used for intra-project communications

Database (MariaDB)      
    used to store project states

From the user viewpoint, OpenStack can be operated by three ways:

- Horizon: the OpenStack service in charge of providing a Web GUI

- The OpenStack CLI

- REST APIs

2.2 EnOS
~~~~~~~~

EnOS is a holistic framework to conduct evaluations of different
OpenStack configurations in an easy and reproducible manner. In
particular, EnOS helps you in deploying real OpenStack instances on
different types of infrastructure (from virtual environments based on
VMs like Vagrant, to real large-scale testbeds composed of bare-metal
machines like Grid’5000), stressing it and getting feedback.

Many projects exist to deploy OpenStack (e.g.
OpenStack-Ansible [4]_ , OpenStack-Chef [5]_ ,
OpenStack Kolla [6]_ , Kubernetes [7]_ ,
Juju [8]_ ). EnOS relies on the Kolla OpenStack project to
deploy OpenStack modules as Docker containers.

EnOS’ workflow is the following:

- ``enos up``: book, provision and bootstrap testbed resources

  - install dependencies (Docker)

  - install monitoring tools (cAdvisor, collectd, influxdb, grafana)

- ``enos deploy``: deploy OpenStack (based on Kolla)

- ``enos bench``: benchmark OpenStack

- ``enos backup``: backup the collected metrics

- ``enos destroy``: release resources

2.3 Topology deployed in this lab
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The lab makes use of EnOS to deploy OpenStack on Grid’5000. In
particular, we will need four G5K machines for our deployment:

- *enos* node: A machine we will deploy ourselves to run EnOS.

- *control* node: A machine that hosts the control modules, projects’
  APIs and databases.

- *network* node: A machine that hosts network agents.

- *compute* node: A machine that manages the compute modules where
  guest VMs live.

Note that while we will deploy the *enos* node ourselves on G5K, but
the three other nodes will be deployed automatically by EnOS. The
following figure depicts the status of the different components in
play during the lab:

::

                           +---------------+
    +----------------------+ g5k-frontend  +----------------------+
    |                      +-------+-------+                      |
    |                              |                              |
    |                              v                              |
    |                      +---------------+                      |
    |           +----------+     enos      +----------+           |
    |           |          +---------------+          |           |
    |           |                  |                  |           |
    |           v                  v                  v           |
    |   +-------+-------+  +-------+-------+  +-------+------ +   |
    |   |    compute    |  |    control    |  |    network    |   |
    |   |               |  |               |  |               |   |
    |   | * container 1 |  | * container 1 |  | * container 1 |   |
    |   | * container 2 |  | * container 2 |  | * container 2 |   |
    |   | * ...         |  | * ...         |  | * ...         |   |
    |   | * container n |  | * container n |  | * container n |   |
    |   +---------------+  +---------------+  +---------------+   |
    |                                                             |
    +-------------------------------------------------------------+


As we can see in this figure, EnOS will be in charge of provisioning
the *compute*, *control* and *network* nodes. In particular, EnOS will
deploy Docker containers inside each nodes, which correspond to
OpenStack services. For instance, the *control* node will host the
``nova-api`` and ``nova-scheduler`` containers while the *compute* node
will host the ``nova-compute`` and ``nova-libvirt`` containers to provide
VM hypervisor mechanisms.

.. note::

    Note that to deploy on G5K, we need a dedicated node to run EnOS
    because it is discouraged to run experiments on the frontend. This
    restriction is meant to avoid disturbing other users that are logged,
    since the frontend node has limited resources. On a regular
    deployment, EnOS could be run directly from your laptop.

3 Set the *enos* node and install EnOS
--------------------------------------

The first step is to determine on which cluster you will deploy
OpenStack. To that end, you can run ``funk`` (Find yoUr Nodes on g5K)
from any frontend to see the availability on G5K:

.. code-block:: sh

    # laptop:~$
    ssh nantes.g5k
    # fnantes:~$
    funk -w 4:00:00

In this example, we check the availability of G5K’s clusters for the
next four hours (adapt the time regarding your situation). Note that
you can adapt the time of your reservation afterward, using the
``oarwalltime`` command [9]_ . Find a cluster with at least
four nodes available before going further. Once it is done, reach the
cluster’s site first, and then, get a new machine which we will use as
our *enos* node. In this document, we target the parapide cluster,
located in the Rennes site:

.. code-block:: sh

    # fnantes:~$
    ssh rennes
    # frennes:~$ -- Not mandatory, but recommended
    tmux
    # frennes:~$ -- Let's connect to the enos node
    oarsub -I -l "nodes=1,walltime=4:00:00" -p "cluster='parapide'"

Here, we get a new machine in interactive mode (*i.e.*,
``-I``) for the next four hours from the parapide cluster. If it
succeeds you should be directly connected to this node (check your
prompt).

.. note::

    Note that we created a ``tmux`` session in order to be resilient to any
    network failure during your ssh session. Whenever you want to restore
    this session, you can connect to the frontend and attach to your tmux
    session, as follows:

    .. code-block:: sh

        # laptop:~$
        ssh rennes.g5k
        # frennes:~$ -- Stands for "tmux attach"
        tmux a

Make a directory from where you will install EnOS and run your
experiments:

.. code-block:: sh

    # enos:~$
    mkdir -p ~/enos-myxp
    # enos:~$
    cd ~/enos-myxp

Then, install EnOS in your working directory (python3.5+ is required):

.. code-block:: sh

    # enos:~/enos-myxp$
    virtualenv --python=python3 venv
    # (venv) enos:~/enos-myxp$
    . venv/bin/activate
    # (venv) enos:~/enos-myxp$
    pip install "enos[openstack]==4.3.0"

.. note::

    Note that EnOS is a Python project. We installed it inside a virtual
    environment, with ``virtualenv``, to avoid any conflict regarding the
    version of its dependencies. Furthermore, it does not install anything
    outside the virtual environment which keeps your OS clean. Remember
    that you have to be in the virtual environment to use EnOS. It means
    that if you open a new terminal, you need to re-enter the venv. For
    instance, now that EnOS is installed, you can come back as follow:

    .. code-block:: sh

        # laptop:~$
        ssh rennes.g5k
        # frennes:~$
        cd ~/enos-myxp
        # frennes:~/enos-myxp$
        source venv/bin/activate

Before going further, check EnOS works by typing ``enos --help``:

::

    Enos: Monitor and test your OpenStack.
    [<args> ...] [-e ENV|--env=ENV]
                [-h|--help] [-v|--version] [-s|--silent|--vv]

    General options:
      -e ENV --env=ENV  Path to the environment directory. You should
                        use this option when you want to link to a specific
                        experiment. Not specifying this value will
                        discard the loading of the environment (it
                        makes sense for `up`).
      -h --help         Show this help message.
      -s --silent       Quiet mode.
      -v --version      Show version number.
      -vv               Verbose mode.

    Commands:
      new            Print a reservation.yaml example
      up             Get resources and install the docker registry.
      os             Run kolla and install OpenStack.
      init           Initialise OpenStack with the bare necessities.
      bench          Run rally on this OpenStack.
      backup         Backup the environment
      ssh-tunnel     Print configuration for port forwarding with horizon.
      tc             Enforce network constraints
      info           Show information of the actual deployment.
      destroy        Destroy the deployment and optionally the related resources.
      deploy         Shortcut for enos up, then enos os and enos config.
      kolla          Runs arbitrary kolla command on nodes
    See 'enos <command> --help' for more information on a specific
    command.

4 Deploy OpenStack using EnOS
-----------------------------

4.1 The EnOS configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To deploy OpenStack, EnOS reads a *configuration file*. This file
states the OpenStack resources you want to deploy/measure together
with their topology. A configuration could say, “Deploy a basic
OpenStack on a single node”, or “Put OpenStack control services on
ClusterA and compute services on ClusterB”, but also “Deploy each
OpenStack services on a dedicated node and add WAN network latency
between them”. So that EnOS can deploy such OpenStack over your
testbed and run performance analysis.

The description of the configuration is done in a ``reservation.yaml``
file. You may generate a new one with ``enos new > reservation.yaml``.
The configuration file is pretty fat, with a configuration sample for
all testbed supported by EnOS (G5k, Chameleon, Vagrant, ...).

Use your favorite text editor to open the ``reservation.yaml`` file, for
instance: ``vim reservation.yaml``, and edit it to fit your situation --
*i.e.*, something like listing `lst:reservation.yaml`_. Three parts of
this configuration file are interested for a simple use of EnOS:

- ``provider`` section (l. 5): Defines on which testbed to
  deploy OpenStack (*i.e.*, G5k, Chameleon, Vagrant, ...).

- ``resources`` section (l. 10): Defines the number and role of
  machines to deploy on the testbed (*e.g.*, book 3 nodes on
  ``paravance`` with 1 ``control`` node, 1 ``network`` node and 1 ``compute``
  node).

- ``kolla`` section (l. 36): Defines the OpenStack
  configuration, for instance:

  - Which OpenStack version to deploy (*e.g.*, ``kolla-ref: "stable/queens"``).

  - Which OpenStack project to enable/disable (*e.g.*, ``enable_heat: "no"``).

.. code-block:: yaml
    :lineno-start: 1
    :name: lst:reservation.yaml

    ---
    # ############################################### #
    # Grid'5000 reservation parameters                #
    # ############################################### #
    provider:                     
      type: g5k
      job_name: 'enos'
      walltime: '04:00:00'

    resources:                    
      paravance:
        compute: 1
        network: 1
        control: 1

    # ############################################### #
    # Inventory to use                                #
    # ############################################### #
    inventory: inventories/inventory.sample

    # ############################################### #
    # docker registry parameters
    # ############################################### #
    registry:
      type: internal


    # ############################################### #
    # Enos Customizations                             #
    # ############################################### #
    enable_monitoring: yes

    # ############################################### #
    # Kolla parameters                                #
    # ############################################### #
    kolla_repo: "https://git.openstack.org/openstack/kolla-ansible" 
    kolla_ref: "stable/queens"

    # Vars : kolla_repo/ansible/group_vars/all.yml
    kolla:
      kolla_base_distro: "centos"
      kolla_install_type: "source"
      docker_namespace: "beyondtheclouds"
      enable_heat: "yes"

The ``provider`` section tells on which testbed to deploy OpenStack plus
its configuration. The configuration may vary from one testbed to
another. For instance, Grid’5000 and Chameleon are research testbed
were resources have to be booked, thus the configuration includes a
``walltime`` to define the time of your reservation. Conversely, the
Vagrant provider starts VM with VirtualBox on your local machine, and
thus doesn’t include such a option. Please, refer to the EnOS provider
documentation [10]_  to find the configuration parameters
depending on the testbed. For the sake of this lab we are going to use
the Grid’5000 provider (*i.e.*, ``type: g5k``). Note that a ``walltime``
of 3 hours is enough for the first part of this workshop. If you plan
to stay for the second part you should set 5 hours

The ``resources`` key contains the description of the desired resources
and their topology. Once again, way you describe your topology may
vary a little bit depending on the testbed you target. Please, refer
to the EnOS provider documentation [10]_  to find examples
of resources description depending on the testbed. Here we declare the
G5K cluster we target (*e.g.*, ``paravance``), as well as the resources
we want to deploy on: a ``control``, a ``network`` and a ``compute`` node on
which will be deployed all the required OpenStack services.

4.2 Deploy OpenStack
~~~~~~~~~~~~~~~~~~~~

EnOS manages all the aspects of an OpenStack deployment by calling
``enos deploy``. Concretely, the ``deploy`` phase first gets resources on
your testbed following your configuration description. Then, it
provisions these resources with Docker. Finally, it starts each
OpenStack services (e.g. Keystone, Nova, Neutron) inside a dedicated
Docker container.

Launch the deployment with:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos deploy -f reservation.yaml

EnOS is now provisioning three machines on the cluster targeted by the
``reservation.yaml``. Once the machines are provisioned, EnOS deploy
OpenStack services on them, and you can display information regarding
your deployment by typing:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos info

In particular, you should see the IP address of the deployed nodes.

While EnOS deploys OpenStack (it takes ~20 to 45 minutes -- there are
way to speed up your deployment [11]_ ), you can
observe EnOS running containers on the control node. For that, you can
access to the control node by typing:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    ssh -l root $(enos info --out json | jq -r '.rsc.control[0].address')
    # control:~# -- List the downloaded Docker images
    docker images
    # control:~# -- List the running Docker containers
    docker ps
    # control:~# -- Go back to `(venv) enos:~/enos-myxp$`
    exit

.. note::

    Note that at the end of your session, you can release your reservation
    by typing:

    .. code-block:: sh

        # (venv) enos:~/enos-myxp$
        enos destroy --hard

    It will destroy all your deployment and delete your reservation.

5 Play with OpenStack
---------------------

The last service deployed is the OpenStack dashboard (Horizon). Once
the deployment process is finished, Horizon is reachable from G5k.
More precisely, Horizon runs in a Docker container on the control
node, and listens on port 80. To access Horizon from your own web
browser (from your laptop), you can create an SSH tunnel from your
laptop to control node, located in G5K. To that end, you first need
to get control node’s IP address, and then create the tunnel. Open a
new terminal and type the following:

1. Find the control node address using EnOS:

   .. code-block:: sh

       # (venv) enos:~/enos-myxp$
       enos info
       # (venv) enos:~/enos-myxp$
       enos info --out json | jq -r '.rsc.control[0].address'

2. Create the tunnel from your laptop:

   .. code-block:: sh

       # laptop:~$ -- `ssh -NL 8000:<g5k-control>:80 <g5k-site>.g5k`, e.g.,
       ssh -NL 8000:paravance-14-kavlan-4.nantes.grid5000.fr:80 rennes.g5k

.. note::

    This lab has been designed to **run on a cluster where nodes have two network interfaces**. **If you plan to run the lab on a cluster with a single network interface**, **please run the following script on the network node**. You can check how many network interfaces are
    associated to a cluster by consulting the `G5k Cheatsheet <https://www.grid5000.fr/mediawiki/images/G5k_cheat_sheet.pdf>`_. If you are
    concerned, connect to the network node as root with:

    .. code-block:: sh

        # (venv) enos:~/enos-myxp$
        ssh -l root $(enos info --out json | jq -r '.rsc.network[0].address')

    And execute the following script:

    .. code-block:: sh

        #!/usr/bin/env bash

        # The network interface
        IF=<interface-network-node-(eno|eth)[0-9]>
        # This is the list of the vip of $IF
        ips=$(ip addr show dev $IF|grep "inet .*/32" | awk '{print $2}')
        if [[ ! -z "$ips" ]]
        then
          # vip detected
          echo $ips
          docker exec -ti openvswitch_vswitchd ovs-vsctl add-port br-ex $IF && ip addr flush $IF && dhclient -nw br-ex
          for ip in $ips
          do
            ip addr add $ip dev br-ex
          done
        else
          echo "nothing to do"
        fi

Once it is done, you can access Horizon from your web browser through
`http://localhost:8000 <http://localhost:8000>`_ with the following credentials:

- login: ``admin``

- password: ``demo``

From here, you can reach ``Project > Compute > Instances > Launch Instance`` and boot a virtual machine given the following information:

- a name (e.g., ``horizon-vm``)

- an image (e.g., ``cirros``)

- a flavor to limit the resources of your instance (I recommend
  ``tiny``)

- and a network setting (must be ``private``)

You should select options by clicking on the arrow on the right of
each possibility. When the configuration is OK, the ``Launch Instance``
button should be enabled. After clicking on it, you should see the
instance in the ``Active`` state in less than a minute.

Now, you have several options to connect to your freshly deployed VM.
For instance, by clicking on its name, Horizon provides a virtual
console under the ``Console`` tab. Use the following credentials to
access the VM:

- login: ``cirros``

- password: ``cubswin:)``

While Horizon is helpful to discover OpenStack features, this is not
how a real operator administrates OpenStack. A real operator prefers
command line interface 😄.

5.1 Unleash the Operator in You
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenStack provides a command line interface to operate your Cloud. But
before using it, you need to set your environment with the OpenStack
credentials, so that the command line won’t bother you by requiring
credentials each time.

Load the OpenStack credentials:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    . current/admin-openrc

You can then check that your environment is correctly set executing
the following command that should output something similar to the
listing `lst:env-os`_:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    env|fgrep OS_|sort

.. code-block:: sh
    :name: lst:env-os

    OS_AUTH_URL=http://10.24.61.255:35357/v3
    OS_IDENTITY_API_VERSION=3
    OS_PASSWORD=demo
    OS_PROJECT_DOMAIN_ID=default
    OS_PROJECT_DOMAIN_NAME=default
    OS_PROJECT_NAME=admin
    OS_REGION_NAME=RegionOne
    OS_TENANT_NAME=admin
    OS_USER_DOMAIN_ID=default
    OS_USER_DOMAIN_NAME=default
    OS_USERNAME=admin

All operations to manage OpenStack are done through one single command
line, called ``openstack``. Doing an ``openstack --help`` displays the
really long list of possibilities provided by this command. The
following gives you a selection of the most often used commands to
operate your Cloud:

List OpenStack running services
    ``openstack endpoint list``

List images
    ``openstack image list``

List flavors
    ``openstack flavor list``

List networks
    ``openstack network list``

List computes
    ``openstack hypervisor list``

List VMs (running or not)
    ``openstack server list``

Get details on a specific VM
    ``openstack server show <vm-name>``

Start a new VM
    ``openstack server create --image <image-name> --flavor <flavor-name> --nic net-id=<net-id> <vm-name>``

View VMs logs
    ``openstack console log show <vm-name>``

Based on these commands, you can use the CLI to start a new tiny
cirros VM called ``cli-vm``:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    openstack server create --image cirros.uec\
                            --flavor m1.tiny\
                            --network private \
                            cli-vm

Then, display the information about your VM with the following command:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    openstack server show cli-vm

Note in particular the status of your VM. This status will go from
``BUILD``: OpenStack is looking for the best place to boot the VM, to
``ACTIVE``: your VM is running. The status could also be ``ERROR`` if you
are experiencing hard times with your infrastructure.

With the previous ``openstack server create`` command, the VM boots with
a private IP. Private IPs are used for communication between VMs,
meaning you cannot ping your VM from the lab machine. Network lovers
will find a challenge here: try to ping the VM from the lab machine.
For the others, you have to manually affect a floating IP to your
machine if you want it pingable from the enos node.

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    openstack server add floating ip\
      cli-vm\
      $(openstack floating ip create public -c floating_ip_address -f value)

You can ask for the status of your VM and its IPs with:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    openstack server show cli-vm -c status -c addresses

Wait one minute or two the time for the VM to boot, and when the state
is ``ACTIVE``, you can ping it on its floating IP and SSH on it:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    ping <floating-ip>
    # (venv) enos:~/enos-myxp$
    ssh -l cirros <floating-ip>

.. note::

    Waiting for the IP to appear and then ping it could be done with a
    bunch of bash commands, such as in listing `lst:query-ip`_.

    .. code-block:: sh
        :name: lst:query-ip


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


        if [[ $RC -ne 0 ]] ; then
            echo "Timeout."; exit 124
        fi

    You can also check that the VM finished to boot by looking at its logs
    with ``openstack console log show cli-vm``. The cirros VM finished to
    boot when last lines are:

    ::

        === cirros: current=0.3.4 uptime=16.56 ===
          ____               ____  ____
         / __/ __ ____ ____ / __ \/ __/
        / /__ / // __// __// /_/ /\ \
        \___//_//_/  /_/   \____/___/
           http://cirros-cloud.net


        login as 'cirros' user. default password: 'cubswin:)'. use 'sudo' for root.
        cli-vm login:

Before going to the next section, play around with the ``openstack`` CLI
and Horizon. For instance, list all the features offered by Nova with
``openstack server --help``. Here are some commands:

1. SSH on ``cli-vm`` using its name rather than its private IP.

   .. code-block:: sh

       # (venv) enos:~/enos-myxp$
       openstack server ssh cli-vm --public --login cirros

2. Create a snapshot of ``cli-vm``.

   .. code-block:: sh

       # (venv) enos:~/enos-myxp$
       nova image-create cli-vm cli-vm-snapshot --poll

3. Delete the ``cli-vm``.

   .. code-block:: sh

       # (venv) enos:~/enos-myxp$
       openstack server delete cli-vm --wait

4. Boot a new machine ``cli-vm-clone`` from the snapshot.

   .. code-block:: sh

       # (venv) enos:~/enos-myxp$
       openstack server create --image cli-vm-snapshot\
                               --flavor m1.tiny\
                               --network private\
                               --wait\
                               cli-vm-clone

6 Stress and Visualize OpenStack Behavior using EnOS
----------------------------------------------------

EnOS not only deploys OpenStack according to your configuration, but
also instruments it with a *monitoring stack*. The monitoring stack
polls performance characteristics of the running services and helps
you to understand the behavior of your OpenStack.

Activating the monitoring stack is as simple as setting the
``enable_monitoring`` to ``yes`` in your ``reservation.yaml``. This key
tells EnOS to deploy two monitoring systems. First,
cAdvisor [12]_ , a tool to collect resource usage of running
containers. Using cAdvisor, EnOS gives information about the
CPU/RAM/Network consumption per cluster/node/service. Second,
Collectd [13]_ , a tool to collect performance data of specific
applications. For instance, Collectd enables EnOS to record the number
of updates that have been performed on the Nova database.

The rest of this section, first shows how to visualize cAdvisor and
Collectd information. Then, it presents tools to stress OpenStack in
order to collect interesting information.

6.1 Visualize OpenStack Behavior
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A popular tool to visualize information provided by cAdvisor and
Collectd (and whatever monitoring system you could use) is
Grafana [14]_ . Grafana is a Web metrics dashboard. A Docker
container is in charge of providing this service inside the control
node. As a consequence, prior being able to be reachable from your
browser, you need to set a tunnel to this service, by typing on your
laptop:

.. code-block:: sh

    # laptop:~$ -- `ssh -NL 3000:<g5k-control>:3000 <g5k-site>.g5k`, e.g.,
    ssh -NL 3000:paravance-14-kavlan-4.nantes.grid5000.fr:3000 nantes.g5k

You can then access Grafana at `http://localhost:3000 <http://localhost:3000>`_ with the
following credentials:

- login: ``admin``

- password: ``admin``

The Grafana dashboard is highly customizable. For the sake of
simplicity, we propose to use our configuration file that you can get
with:

.. code-block:: sh

    # laptop:~$
    curl -O http://enos.irisa.fr/tp-g5k/grafana_dashboard.json

You have then to import this file into Grafana. First, click on the
``Grafana logo > + > Import > Upload .json file`` and select the
``grafana_dashboard.json`` file. Next, make names of the right column
matching names of the left column by selecting the good item in the
list. And finish by clicking on Save & Open. This opens the dashboard
with several measures on Nova, Neutron, Keystone, RabbitMQ, ...
services. Keep the dashboard open until the end of the lab, you will
see consumption variation as we will perform stress tests.

6.2 Benchmark OpenStack
~~~~~~~~~~~~~~~~~~~~~~~

Stressing a Cloud manager can be done at two levels: at the *control plane* and at the *data plane*, and so it is for OpenStack. The
control plane stresses OpenStack API. That is to say, features we used
in the previous section to start a VM, get a floating IP, and all the
features listed by ``openstack --help``. The data plane stresses the
usage of resources provided by an OpenStack feature. For instance, a
network data plane testing tool will measure how resources provided by
Neutron handle networks communications.

OpenStack comes with dedicated tools that provide workload to stress
control and data plane. The one for control plane is called
Rally [15]_  and the one for data plane is called
Shaker [16]_ . And these two are well integrated into EnOS.

EnOS looks inside the ``workload`` directory for a file named ``run.yml``.

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    mkdir -p workload
    # (venv) enos:~/enos-myxp$
    touch workload/run.yml

Edit the file ``run.yml`` with your favorite editor. An example of such
a file is given in listing `lst:run.yml`_. The ``rally`` (l. 2) key
specifies the list of ``scenarios`` (l. 9) to execute (here, only
the `8.1 Nova scenario for Rally`_ -- available at
``~/enos-myxp/workload/nova-boot-list-cc.yml`` -- that asks Nova to boot
VMs and list them) and their customization.

The customization could be done by using the top level ``args`` (l.
4). In such case, it applies to any scenario. For instance
here, ``concurrency`` (l. 5) and ``times`` (l. 7) tells Rally
to launch ``5`` OpenStack client for a total of ``10`` execution of every
scenario. The customization could also be done on a per-scenario basis
with the dedicated ``args`` (l. 12), and thus could be only
applies to the specific scenario. For instance here, the ``30`` value
overrides the ``sla_max_avg_duration`` default value solely in the ``boot and list servers`` scenario.

.. code-block:: yaml
    :lineno-start: 1
    :name: lst:run.yml

    ---
    rally:                                   
        enabled: yes
        args:                                
          concurrency:                       
            - 5
          times:                             
            - 10
        scenarios:                           
          - name: boot and list servers
            file: nova-boot-list-cc.yml
            args:                            
              sla_max_avg_duration: 30
    shaker:
      enabled: yes                           
      scenarios:
        - name: OpenStack L3 East-West Dense
          file: openstack/dense_l3_east_west

Calling Rally and Shaker from EnOS is done with:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos bench --workload=workload

.. note::

    At the same time as enos bench is running, keep an eye on the Grafana
    dashboard available at `http://localhost:3000 <http://localhost:3000>`_. At the top left of the
    page, you can click on the clock icon ⌚ and tells Grafana to
    automatically refresh every 5 seconds and only display the last 5
    minutes.

Rally and Shaker provide a huge list of scenarios on their respective
GitHub [17]_  [18]_ . Before going further,
go through the Rally list and try to add the scenario of your choice
into the ``run.yml``. Note that you have to download the scenario file
in the ``workload`` directory and then put a new item under the
``scenarios`` key (l. 9) . The new item should contain, at least,
the ``name`` of the scenario and its ``file`` path (relative to the
``workload`` directory).

6.3 Backup your results
~~~~~~~~~~~~~~~~~~~~~~~

Rally and Shaker produce reports on executed scenarios. For instance,
Rally produces a report with the full duration, load mean duration,
number of iteration and percent of failures, per scenario. These
reports, plus data measured by cAdvisor and Collectd, plus logs of
every OpenStack services can be backup by EnOS with:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos backup --backup_dir=benchresults

The argument ``backup_dir`` tells where to store backup archives. If you
look into this directory, you will see, among others, an archive named
``<controler-node>-rally.tar.gz``. Concretely, this archive contains a
backup of Rally database with all raw data and the Rally reports. You
can extract the Rally report of the *Nova boot and list servers*
scenario with the following command and then open it in your favorite
browser:

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    tar --file benchresults/*-rally.tar.gz\
        --get $(tar --file benchresults/*-rally.tar.gz\
                    --list | grep "root/rally_home/report-nova-boot-list-cc.yml-.*.html")

For those interested in playing with deploying applications on top of
OpenStack, you can jump to another workshop involving Heat: the
OpenStack Orchestration service `here <http://enos.irisa.fr/tp-g5k/HEAT-SUBJECT.html>`_.

7 Add Traffic Shaping
---------------------

EnOS allows to enforce network emulation in terms of latency,
bandwidth limitation and packet loss.

7.1 Define Network Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Network constraints (latency/bandwidth limitations) are enabled by the
use of groups of nodes. Resources must be described using a ``topology``
description instead of a ``resources`` description. For instance,
listings `lst:topos-g5k`_ defines two groups named ``grp1`` and ``grp2``.

.. code-block:: yaml
    :name: lst:topos-g5k

    topology:
      grp1:
        paravance:
          control: 1
          network: 1
      grp2:
        paravance:
          compute: 1

Constraints are then described under the ``network_constraints`` key in
the ``reservation.yaml`` file:

.. code-block:: yaml
    :name: lst:net-constraints

    network_constraints:
      enable: true
      default_delay: 25ms
      default_rate: 100mbit
      default_loss: 0.1%
      constraints:
        - src: grp1
          dst: grp2
          delay: 50ms
          rate: 1gbit
          loss: 0%
          symmetric: true

Copy your ``reservation.yaml`` file as ``reservation-topo.yaml`` with ``cp reservation.yaml reservation-topo.yaml`` and edit it to include the
topology and network constraints definition. An example of such file
is given in `8.2 Configuration file with a topology and network constraints`_.

Since our topology is now defined by groups, we need to re-run ``enos deploy -f reservation-topo.yaml`` (which should be faster than the
first time). And then enforce these constraints with ``enos tc``, which
results in:

- Default network delay is 50ms.

- Default bandwidth is 100Mbit/s.

- Default packet loss percentage is 0.1%.

- Network delay between machines of ``grp1`` and ``grp2`` is 100ms
  (2x50ms: symmetric).

- Bandwidth between machines of ``grp1`` and ``grp2`` is 1 Gbit/s.

- Packet loss percentage between machines of ``grp1`` and ``grp2`` is 0%.

.. note::

    Invoking ``enos tc --test`` generates various reports that validate the
    correct enforcement of the constraints. They are based on ``fping`` and
    ``flent`` latency and bandwidth measurements respectively. The report is
    located in the
    ``~/enos-myxp/current/_tmp_enos_/<g5k-(control|network|compute)>.out``.

7.2 Run Dataplane Benchmarks with and without DVR
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the Shaker ``dense_l3_east_west`` scenario with

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos bench --workload=workload

.. note::

    If you look carefully, you will see that execution of Nova boot and
    list fails because of a SLA violation. You can try to customize
    listing `lst:run.yml`_ to make the test pass.

In this scenario Shaker launches pairs of instances on the same
compute node. Instances are connected to different tenant networks
connected to one router. The traffic goes from one network to the
other (L3 east-west). Get the Shaker report with ``enos backup`` and
analyze it. You will remark that network communications between two
VMs co-located on the same compute are 100ms RTT. This is because
packet are routed by Neutron service that is inside ``grp1`` and VMs are
inside the ``grp2``.

Now, reconfigure Neutron to use DVR [19]_ . DVR will push Neutron
agent directly on the compute of ``grp2``. With EnOS, you should do so
by updating the ``reservation.yaml`` and add ``enable_neutron_dvr: "yes"``
under the ``kolla`` key.
Then, tell EnOS to reconfigure Neutron.

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos os --tags=neutron --reconfigure

And finally, re-execute the ``dense_l3_east_west`` scenario.

.. code-block:: sh

    # (venv) enos:~/enos-myxp$
    enos bench --workload=workload

Compare this result with the previous one. You see that you no more
pay the cost of WAN latency.

This experiment shows the importance of activating DVR in a WAN
context, and how you can easily see that using EnOS. Do not hesitate
to take a look at the complete list of Shaker scenarios on their
GitHub [18]_  and continue to have fun with EnOS.

8 Appendix
----------

8.1 Nova scenario for Rally
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    {% set image_name = image_name or "cirros.uec" %}
    {% set flavor_name = flavor_name or "m1.tiny" %}
    {% set sla_max_avg_duration = sla_max_avg_duration or 60 %}
    {% set sla_max_failure = sla_max_failure or 0 %}
    {% set sla_max_seconds = sla_max_seconds or 60 %}
    ---
      NovaServers.boot_and_list_server:
        -
          args:
            flavor:
              name: {{flavor_name}}
            image:
              name: {{image_name}}
            detailed: true
            auto_assign_nic: true
          runner:
            concurrency: {{concurrency}}
            times: {{times}}
            type: "constant"
          context:
            users:
              tenants: 1
              users_per_tenant: 1
            network:
              start_cidr: "10.2.0.0/24"
              networks_per_tenant: 1
            quotas:
              neutron:
                network: -1
                port: -1
              nova:
                instances: -1
                cores: -1
                ram: -1
          sla:
            max_avg_duration: {{sla_max_avg_duration}}
            max_seconds_per_iteration: {{sla_max_seconds}}
            failure_rate:
              max: {{sla_max_failure}}

8.2 Configuration file with a topology and network constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    ---
    # ############################################### #
    # Grid'5000 reservation parameters                #
    # ############################################### #
    provider:
      type: g5k
      job_name: 'enos'
      walltime: '04:00:00'

    topology:
      grp1:
        paravance:
          control: 1
          network: 1
      grp2:
        paravance:
          compute: 1

    network_constraints:
      enable: true
      default_delay: 25ms
      default_rate: 100mbit
      default_loss: 0.1%
      constraints:
        - src: grp1
          dst: grp2
          delay: 50ms
          rate: 1gbit
          loss: 0%
          symmetric: true

    # ############################################### #
    # Inventory to use                                #
    # ############################################### #
    inventory: inventories/inventory.sample

    # ############################################### #
    # docker registry parameters
    # ############################################### #
    registry:
      type: internal
      ceph: true
      ceph_keyring: /home/discovery/.ceph/ceph.client.discovery.keyring
      ceph_id: discovery
      ceph_rbd: discovery_kolla_registry/datas
      ceph_mon_host:
        - ceph0.rennes.grid5000.fr
        - ceph1.rennes.grid5000.fr
        - ceph2.rennes.grid5000.fr

    # ############################################### #
    # Enos Customizations                             #
    # ############################################### #
    enable_monitoring: yes

    # ############################################### #
    # Kolla parameters                                #
    # ############################################### #
    kolla_repo: "https://git.openstack.org/openstack/kolla-ansible"
    kolla_ref: "stable/queens"

    # Vars : kolla_repo/ansible/group_vars/all.yml
    kolla:
      kolla_base_distro: "centos"
      kolla_install_type: "source"
      docker_namespace: "beyondtheclouds"
      enable_heat: "yes"


.. [1] `https://www.openstack.org/ <https://www.openstack.org/>`_

.. [2] `https://hal.inria.fr/hal-01415522v2 <https://hal.inria.fr/hal-01415522v2>`_

.. [3] `https://enos.readthedocs.io/en/stable/ <https://enos.readthedocs.io/en/stable/>`_

.. [4] `https://github.com/openstack/openstack-ansible <https://github.com/openstack/openstack-ansible>`_

.. [5] `https://github.com/openstack/openstack-chef-repo <https://github.com/openstack/openstack-chef-repo>`_

.. [6] `https://docs.openstack.org/developer/kolla-ansible/ <https://docs.openstack.org/developer/kolla-ansible/>`_

.. [7] `https://github.com/stackanetes/stackanetes <https://github.com/stackanetes/stackanetes>`_

.. [8] `https://jujucharms.com/openstack <https://jujucharms.com/openstack>`_

.. [9] `https://www.grid5000.fr/mediawiki/index.php/Advanced_OAR#Changing_the_walltime_of_a_running_job <https://www.grid5000.fr/mediawiki/index.php/Advanced_OAR#Changing_the_walltime_of_a_running_job>`_

.. [10] `https://enos.readthedocs.io/en/stable/provider/index.html <https://enos.readthedocs.io/en/stable/provider/index.html>`_

.. [11] `https://enos.readthedocs.io/en/stable/customization/index.html#internal-registry <https://enos.readthedocs.io/en/stable/customization/index.html#internal-registry>`_

.. [12] `https://github.com/google/cadvisor <https://github.com/google/cadvisor>`_

.. [13] `https://collectd.org/ <https://collectd.org/>`_

.. [14] `https://grafana.com/ <https://grafana.com/>`_

.. [15] `https://rally.readthedocs.io/en/latest/ <https://rally.readthedocs.io/en/latest/>`_

.. [16] `https://pyshaker.readthedocs.io/en/latest/ <https://pyshaker.readthedocs.io/en/latest/>`_

.. [17] `https://github.com/openstack/rally/tree/master/rally/plugins/openstack/scenarios <https://github.com/openstack/rally/tree/master/rally/plugins/openstack/scenarios>`_

.. [18] `https://github.com/openstack/shaker/tree/master/shaker/scenarios/openstack <https://github.com/openstack/shaker/tree/master/shaker/scenarios/openstack>`_

.. [19] `https://wiki.openstack.org/wiki/Neutron/DVR <https://wiki.openstack.org/wiki/Neutron/DVR>`_
