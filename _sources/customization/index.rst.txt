.. _customizations:

Customizations
==============


Changing Kolla version
-----------------------------------

The ``kolla-ansible`` parameter in the configuration file refers to
the package to install (with ``pip``).  All the following are valid
values:
* a PyPi package

  .. code-block:: yaml

     kolla-ansible: kolla-ansible~=12.0

* a git repository to the Ussuri specific version of OpenStack

  .. code-block:: yaml

     kolla-ansible: git+https://github.com/openstack/kolla-ansible.git@stable/ussuri

* an editable version of the latest kolla-ansible code (bleeding edge)

  .. code-block:: yaml

     kolla-ansible: -e git+https://opendev.org/openstack/kolla-ansible.git@master


* an editable version to a local directory that contains the
  kolla-ansible source code (best to patch kolla-ansible)

  .. code-block:: yaml

     kolla-ansible: -e ~/path/to/loca/kolla-ansible


Customize Kolla variables
-----------------------------------

Custom kolla-ansible parameters can be put in the configuration file
under the key ``kolla``. For instance, Kolla enables Heat by default
through the ``enable_heat`` parameter.  Enos tells Kolla to **not**
deploy Heat by overriding the default parameter as following:

.. code-block:: yaml

    kolla:
      enable_heat: "no"

The complete list of kolla-ansible variables can be found `here
<https://opendev.org/openstack/kolla-ansible/src/branch/master/etc/kolla/globals.yml>`_.

Note on the network interfaces:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Providers do their best to configure the network decently. This probably doesn't
cover all the possible use cases. But, if you know what interfaces are configured by
the provider you can specify a more precise allocation under the ``kolla`` key.
For instance:

.. code-block:: yaml

    kolla:
      network_interface: eth1
      neutron_external_interface: eth2
      tunnel_interface: eth3

Changing the topology
---------------------

Let's assume you want to run the ``nova-conductor`` in a dedicated node:

1. Add a new node reservation in the configuration file:

.. code-block:: yaml

    paravance:
      control: 1
      network: 1
      compute: 1
      conductor-node: 1

2. Create an new inventory file in the ``inventories`` subdirectory
(copy paste the sample inventory) and change the group of the
conductor service:

.. code-block:: bash

    [nova-conductor:children]
    conductor-node

3. In the configuration file, points the inventory to use to this new
inventory.

4. Launch the deployment as usual, and you'll get the ``nova-conductor``
on a dedicated node.

Ansible configuration
----------------------

By default, Enos loads its own ``ansible.cfg``. To use another Ansible
configuration file, the ``ANSIBLE_CONFIG`` environment variable can be used.
Further information can be found : `see here
<http://docs.ansible.com/ansible/intro_configuration.html>`_.


Docker version customization
----------------------------

Kolla-ansible tightly integrates with the Docker API, and major versions
of Docker have been known to cause Kolla-ansible to fail.

Enos selects and installs an appropriate version of Docker on target nodes,
but if you know what you are doing, you can force a specific version:

.. code-block:: yaml

    docker_version: 24.0


Docker registry mirror configuration
------------------------------------

EnOS can deploy a docker registry mirror in different ways. This is controlled
by the configuration file.

No Registry mirror
~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    registry:
      type: none

With the above configuration, EnOS won't deploy any registry mirror. Any docker
agent in the deployment will use Docker Hub.

Internal Registry mirror
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    registry:
      type: internal

With the above configuration, EnOS deploys a fresh registry that acts as a
private docker registry mirroring the official one and cache images close to
your deployment resources.

External Registry mirror
~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: yaml

    registry:
      type: external
      ip: 192.168.142.253
      port: 5000

With the above configuration, EnOS will configure all the docker agents to access
the registry located at `registry.ip:registry:port`. Note that registry must be
an insecure registry.

.. note ::

  If you deploy the external registry mirror on the controller node of
  OpenStack, make sure the port 5000 don't collide with the port of Keystone.

  When using EnOS locally, it's a good idea to keep a separated external registry to
  speed up the deployment.

.. note ::

  With the Grid'5000 provider we recommend to use the Grid'5000
  mirror.

  .. code-block:: yaml

     registry:
       type: external
       ip: docker-cache.grid5000.fr
       port: 80


Single interface deployment
---------------------------

Please refer to this discussion :  https://github.com/BeyondTheClouds/enos/issues/227
