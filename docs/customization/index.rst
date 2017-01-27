Customizations
==============


Changing Kolla / Ansible variables
-----------------------------------

Custom Kolla / Ansible parameters can be put in the configuration file
under the key ``kolla``. For instance, Kolla uses the
``openstack_release`` parameter to fix the OpenStack version to deploy.
So, Enos tells Kolla to deploy the ``3.0.2`` version with:

.. code-block:: yaml

    kolla:
      openstack_release: "3.0.2"

Note that the Kolla code varies from one version of OpenStack to
another. You should always target a version of Kolla code that
support the deployment of the expected OpenStack. To do so, you can
change the git repository/reference of Kolla code with:

.. code-block:: yaml

    kolla_repo: "https://git.openstack.org/openstack/kolla"
    kolla_ref: "stable/newton"

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

