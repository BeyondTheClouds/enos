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
OpenStack on. Information in the provider description tells Enos where
these resources are and how to access to them. Concretely, you have to
ensure that following information are present in the
``reservation.yaml`` file from the :ref:`installation` section to
properly configure Enos with already running resources.

.. code-block:: yaml

   provider:  # Configuration for the static provider
              # All keys are mandatory
     type: static
     network:
       extra_ips: # Array of (virtual) IPs to be assigned
                  # during the deployment (e.g HAProxy)
                  # At least 5 IPs routable through the
                  # APIs interface
                  - 198.51.100.49
                  - 198.51.100.50
                  - 198.51.100.51
                  - 198.51.100.52
                  - 198.51.100.53
       # Openstack external network will be configured according
       # to the following keys/values. IPs have to be routable through
       # the external interface
       start:   203.0.113.17     # First available IP
       end:     203.0.113.31     # Last available IP
       cidr:    203.0.113.16/28  # cidr notation to describe the pool of IPs
       gateway: 203.0.113.254    # IP address of the gateway
       dns:     203.0.113.253    # IP address of the DNS
     eths:
       - eth1   # Name of the APIs interface
       - eth2   # Name of the external interface
   resources: # An object with roles and there associated resources
     control:   # The role control, followed by resource info:
       address:   192.0.2.17  # IP of the control node
       alias:     control   # Name for the node (optional, default to address)
       user:      user      # ssh user name (optional, default to ssh config)
       keyfile:   keyfile   # path to ssh private key (optional, default to ssh config)
       port:      22        # ssh port (optional, default to ssh config)
       extra:   # Extra variables passed to ansible (optional, default to none)
         ansible_become: yes  # (optional, use "yes" if the user need to use sudo)
     compute:   # A role can also have a list of resources
       - address: 192.0.2.33  # IP address of the first compute
         alias:   compute1  # ...
         user:    user      # ...
         keyfile: keyfile   # ...
         port:    22        # ...
       - address: 192.0.2.34  # IP address of the second compute
       - address: 192.0.2.35  # IP address of the third compute
     network:
       - address: 192.0.2.17  # IP address of the first network host

All the hosts must have an IP address already configured on the APIs
interface matching the networks defined in ``reservation.yml``
under ``network``, for example: 198.51.100.17 for the ``control``
host, 198.51.100.33 for the ``compute1`` host and so on.

In the ``resources`` there must be at least one host entry for each of
the following names:

- control
- compute
- network

The same host can be assigned to different ``resources``.  In this
case using the ``yaml`` syntax with anchors and alias will help you to
reach a DRY configuration:

.. code-block:: yaml

   # Four our convenience we define all the hosts here, and then map them
   # to the resources, keys are arbitrary, yaml syntax does not support
   # anchoring an item in a list

   hosts:
     1: &h1
       address: 192.0.2.17
       user: ubuntu
       extra:
         ansible_become: yes
     2: &h2
       address: 192.0.2.33
       user: ubuntu
       extra:
         ansible_become: yes
     3: &h3
       address: 192.0.2.34
       user: ubuntu
       extra:
         ansible_become: yes

   resources:
     control:
       - *h1
     compute:
       - *h2
       - *h3
     network:
       - *h1
     storage:
       - *h2
       - *h3
