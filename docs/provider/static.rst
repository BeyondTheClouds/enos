.. _static:

Static
======

The static provider reuses already available resources (machines, network) to
deploy OpenStack on.

Installation
------------

Refer to the :ref:`installation` section to install Enos.

Configuration
-------------

The static provider requires already running resources to deploy
OpenStack on. Information in the provider description tells Enos
where these resources are and how to access to them. Concretely, you
have to fill the following information to properly configure Enos with
already running resources.

.. code-block:: yaml

   provider:  # Configuration for the static provider
              # All keys are mandatory
     type: static
     networks: # An array of networks
     # one network looks like the following
       cidr: 192.168.0.0/24,
     # in case Enos needs to pick ips
     #  e.g : Kolla vips, Openstack ext-net ...
       start: 192.168.0.10,
       end: 192.168.0.50,
     # same as above but used in case you don't have
     # a contiguous set of ips
       extra_ips: []
       dns: 8.8.8.8,
       gateway: 192.168.0.254
     # optionnaly the mapping to a kolla network can be specified
        mapto: <one kolla network name>


   resources: # An object with roles and there associated resources
     control:   # The role control, followed by resource info:
       address:   # Ip of the control node
       alias:     # Name for the node (optional)
       user:      # ssh user name (optional)
       keyfile:   # path to ssh private key (optional)
       port:      # ssh port (optional)
       extra:     # Extra variables passed to ansible (optional)
         ansible_become: yes

     compute:   # A role can also have a list of resources
       - address: # Ip address of the first compute
         alias:   # ...
         user:    # ...
         keyfile: # ...
         port:    # ...
       - address: # Ip address of the second compute
       - address: # Ip address of the third compute
