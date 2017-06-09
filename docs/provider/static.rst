.. _static:

Static
======

The static provider reuses already running resources to deploy
OpenStack on.

Installation
------------

Refer to the :ref:`installation` section to install Enos.

Configuration
-------------

The static provider requires already running resources to deploy
OpenStack on. Information in the provider description then tells Enos
where these resources are and how to access to theme. Concretely, you
have to fill the following information to properly configure Enos with
already running resources.

.. code-block:: yaml

   provider:  # Configuration for the static provider
              # All keys are mandatory
     type: static
     network: # Defines IP pool to create an OpenStack network
       start:   # First available ip
       end:     # Last available ip
       cidr:    # cidr notation to describe the pool of ips
       gateway: # Ip address of the gateway
       dns:     # Ip address of the DNS
     eths:
       - eth1   # Name of the fqdn interface
       - eth2   # Name of the external interface

   resources: # An object with roles and there associated resources
     control:   # The role control, followed by resource info:
       address:   # Ip of the control node
       alias:     # Name for the node (optional)
       user:      # ssh user name (optional)
       keyfile:   # path to ssh private key (optional)
       port:      # ssh port (optional)
     compute:   # A role can also have a list of resources
       - address: # Ip address of the first compute
         alias:   # ...
         user:    # ...
         keyfile: # ...
         port:    # ...
       - address: # Ip address of the second compute
       - address: # Ip address of the third compute
