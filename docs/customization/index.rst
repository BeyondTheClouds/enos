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

Note on the network interfaces:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Providers do their best to configure the network decently. This probably doesn't
cover all the possible use cases. But, if you know what interfaces are configured by
the provider you can specify a more precise allocation under he ``kolla`` key.
For instance :

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

Configuration tuning
--------------------

At some point, Kolla default parameters won't fit your needs. Kolla
provides a mechanism to override custom section of configuration files
but isn't applicable in our case (at least in the corresponding
branch). So we implement a *quick and dirty* way of patching Kolla
code to enable custom configuration files to be used (and by extension
custom kolla code). See the possible patch declaration in
``ansible/group_vars/all.yml``. Patches should be added in the
configuration file of the experiment.


Ansible configuration
----------------------

By default, Enos loads its own ``ansible.cfg``. To use another Ansible
configuration file, the ``ANSIBLE_CONFIG`` environment variable can be used.
Further information can be found : `see here 
<http://docs.ansible.com/ansible/intro_configuration.html>`_.

