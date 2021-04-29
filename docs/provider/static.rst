.. _static:

Static
======

The static provider reuses already available resources (machines, network) to
deploy OpenStack on.

Installation
------------

Refer to the :ref:`installation` section to install Enos. Then do:

.. code-block:: bash

    $ enos new --provider=static
    $ enos deploy


Configuration
-------------

The static provider requires already running resources to deploy
OpenStack on. Information in the provider description tells Enos where
these resources are and how to access to them.

The following shows an example of possible description. It can serve as basis to
build your own configuration that will fit your environment.

.. literalinclude:: ../../tests/functionnal/tests/static/reservation.yaml
   :language: yaml
   :linenos:

Note that the above example is based on running machines given by vagrant and
the libvirt provider following this :download:`Vagrantfile
<../../tests/functionnal/tests/static/Vagrantfile>`

In the ``resources`` there must be at least one host entry for each of
the following names:

- control
- compute
- network

In the ``networks`` section of the provider, a network with role
`network_interface` must be define. For more information on network roles please
refer to the `kolla documentation <https://docs.openstack.org/kolla-ansible/latest/admin/production-architecture-guide.html#network-configuration>`_.
