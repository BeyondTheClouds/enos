Customizations
==============


Changing Kolla / Ansible variables
-----------------------------------

Custom Kolla / Ansible parameters can be put in the configuration file under
the key ``kolla``. The complete list of Kolla variables can be found `here
<https://github.com/openstack/kolla-ansible/blob/master/ansible/group_vars/all.yml>`_.

For instance, Kolla uses the ``openstack_release`` parameter to fix the
OpenStack version to deploy.  So, Enos tells Kolla to deploy the ``4.0.0``
version with:

.. code-block:: yaml

    kolla:
      openstack_release: "4.0.0"

Note that the Kolla code varies from one version of OpenStack to
another. You should always target a version of Kolla code that
support the deployment of the expected OpenStack. To do so, you can
change the git repository/reference of Kolla code with:

.. code-block:: yaml

    kolla_repo: "https://git.openstack.org/openstack/kolla-ansible"
    kolla_ref: "stable/ocata"

You can also your own local clone of kolla-ansible with:

.. code-block:: yaml

    kolla_repo: "file:///path/to/local/kolla-ansible"

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

Running from kolla/master
~~~~~~~~~~~~~~~~~~~~~~~~~~

if you want to live on the bleeding edge you can run the latest Kolla code with
the latest built kolla images.

.. code-block:: yaml

    kolla_repo: "https://git.openstack.org/openstack/kolla-ansible"
    kolla_ref: "master"

    kolla:
      docker_namespace: "beyondtheclouds"
      openstack_release: "latest"


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

Configuration tuning
--------------------

At some point, Kolla default parameters won't fit your needs. Kolla
provides a mechanism to override custom section of configuration files
but isn't applicable in our case (at least in the corresponding
branch). So we implement a *quick and dirty* way of patching Kolla
code to enable custom configuration files to be used (and by extension
custom kolla code). See the possible patch declaration in
``ansible/group_vars/all.yml``. Patches should be added in the
configuration file of the experiment and you can rely on the ``{{ cwd
}}`` key to link patches in your current working directory.

For instance, adding the following in the configuration file tells
enos to look into the current working directory for a file called
``mariadb_boostrap.yml`` that will replace the kolla-ansible mariadb
start playbook.


.. code-block:: yaml

   patches:
   - name: Patch mariadb start
     src: "{{ cwd }}"/mariadb_bootsrap.yml
     dst: kolla/ansible/roles/mariadb/tasks/start.yml
     enabled: "yes"



Ansible configuration
----------------------

By default, Enos loads its own ``ansible.cfg``. To use another Ansible
configuration file, the ``ANSIBLE_CONFIG`` environment variable can be used.
Further information can be found : `see here
<http://docs.ansible.com/ansible/intro_configuration.html>`_.


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

This kind of registry can be made persistent by making sure the underlying
storage backend is persitent. Historically, it has been provided on Grid5000 by
linking a Ceph Rados Block to the registry backend. Thus you can use the
following:

.. code-block:: yaml

    registry:
      type: internal
      ceph: true
      ceph_keyring: path to your keyring
      ceph_id: your ceph id
      ceph_rbd: rbd in the form "pool/rbd"
      ceph_mon_host: list of ceph monitor addresses

.. note ::

   The ``reservation.yaml.sample`` file provides an example of Ceph
   configuration that relies on the G5k Ceph of Rennes. `The G5k Ceph
   tutorial <https://www.grid5000.fr/mediawiki/index.php/Ceph>`_ will
   guide you to create your own Rados Block Device.


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


Single interface deployment
---------------------------

Please refer to this discussion :  https://github.com/BeyondTheClouds/enos/issues/227

