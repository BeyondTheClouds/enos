.. _openstack:

Openstack
=========

The OpenStack provider allows you to use Enos on an OpenStack cloud. In other
words this lets you run OpenStack on OpenStack. In the following, the
under-cloud is the underlying OpenStack infrastructure, the over-cloud is
the OpenStack configured by Enos.

The over-cloud configured by Enos needs a set of resources to be present on the
under-cloud. The first step in the deployment workflow consists in checking or
creating such resources.  Some resources are mandatory and must be present
before the deployment (base image, keypairs, ...), some others can be created
or reused during the deployment (private networks).
For the latter, you can use the default values set by the provider.

For specific under-clouds (e.g Chameleon), specific providers deriving from the
OpenStack provider may be used. They will enforce more default values that fit
the under-cloud specificities (e.g specific DNS, base image, ...)

Installation
-------------

Please refer to :ref:`installation`.

Configuration
-------------

The provider relies on flavor names to group the wanted resources. For
example the following is probably a valid resources description.

.. code-block:: yaml

    provider:
      type: openstack
      <options see below>

    resources:
      m1.medium:
        control: 1
        network: 1
      m1.small:
        compute: 10

Default provider configuration
------------------------------

The OpenStack provider is shipped with the following default options.
These options will be set automatically and thus may be omitted in the
configuration file.

.. code-block:: yaml

    provider:
      type: openstack
      # True if Enos needs to create a dedicated network to work with
      # False means you already have a network, subnet and router to
      # your ext_net configured
      configure_network: true

      # Name of the network to use or to create
      # It will be use as external network for the upper-cloud
      network: {'name': 'enos-network'}

      # Name of the subnet to use or to create
      subnet: {'name': 'enos-subnet', 'cidr': '10.87.23.0/24'}

      # DNS server to use when creating the network
      dns_nameservers: ['8.8.8.8', '8.8.4.4']

      # Floating ips pool
      allocation_pool: {'start': '10.87.23.10', 'end': '10.87.23.100'}

      # Whether one machine must act as gateway
      # - False means that you can connect directly to all the machines
      # started by Enos
      # - True means that one machine will be assigned a floating ip and used
      # as gateway to the others
      gateway: true

These options can be overriden in the provider config.

Mandatory provider configuration
---------------------------------

The following parameters must be present in your configuration file

.. code-block:: yaml

    provider:
      type: openstack
      key_name:          # the ssh keypair name to use
      image_name:        # base image to use to boot the machines from
                         # debian8 or ubuntu16.04
      user:              # user to use when connecting to the machines
      network_interface: # network interface of the deployed machines

Deployment
----------

Enos will interact with the remote OpenStack APIs. In order to get authenticated
you must source your rc file. To use Enos on Openstack there are two distinct
cases :

* If you have direct access to all your machines (:code:`gateway: false`), you can
  launch the deployment with :


.. code-block:: bash

    python -m enos.enos deploy

.. hint::

    In this case, prior to the Enos deployment, you have probably started a
    machine to act as a frontend. This machine is in the same network as those
    used by Enos

* If you don't have direct access to all your machines (:code:`gateway: true`)

`init` phase rely on accessing the OpenStack APIs of the over Cloud. If you
choose to deploy from your local machine, those APIs are probably unreachable.
Check the floating ip assigned to one of your machine and create a proxy
socks.


.. code-block:: bash

    # terminal 1
    python -m enos.enos up
    python -m enos.enos os

    # terminal 2
    ssh -ND 2100 user@<floating-ip>

    # terminal 1
    export http_proxy=socks5://127.0.0.1:2100
    pip install requests[socks] # install requests support to socks
    python -m enos.enos init

Note that the proxy socks allows you to use any `openstack` command directly to
the over-cloud.

Chameleon Cloud (Bare Metal)
=============================

This provider is an OpenStack based provider where some options are set to fit the following platforms :

* https://chi.uc.chameleoncloud.org/
* https://chi.tacc.chameleoncloud.org/


Deployment
----------

You need to install `python-blazarclient` to interact with the lease system of Chameleon :

.. code-block:: bash

    pip install git+https://github.com/openstack/python-blazarclient

Configuration
-------------

As more default values can be enforced automatically, the following is a valid resources description.

.. code-block:: yaml

    provider:
      type: chameleonbaremetal
      key_name: 'enos-key' # must be present prior to the execution

      resources:
        storage: # use "storage" machine type for these roles
          control: 1
          network: 1
        compute: # use "compute" machine type for these roles
          compute: 10

Note that on Chameleon, they are two groups of machines : compute and storage.

Default provider configuration
------------------------------

The following options will be set automatically and thus may be omitted in the
configuration file.

.. code-block::  yaml

    provider:
      type: chameleonbaremetal
      # Name of the Blazar lease to use
      lease_name: enos-lease
      image_name: CC-Ubuntu16.04
      user: cc
      configure_network: False
      network: {name: sharednet1}
      subnet: {name: sharednet1-subnet}
      dns_nameservers: [130.202.101.6, 130.202.101.37]
      # Name of the network interface available on the nodes
      network_interface: eno1
      # Experiment duration
      walltime: "02:00:00"

These options can be overriden in the provider config.

On https://chi.tacc.chameleoncloud.org/ the subnet must be :code:`subnet: {'name': 'shared-subnet1'}`


.. warning ::

    A shared-network is used and may limit the features of the over-cloud (e.g floating ips)

Chameleon Cloud (KVM)
=====================

This provider is an OpenStack based provider where some options are set to fit
the folllowing platform :

* https://openstack.tacc.chameleoncloud.org

Configuration
-------------

As more default values can be enforced automatically, the following is a valid resources description.

.. code-block:: yaml

    provider:
      type: chameleonkvm
      key_name: 'enos-key' # must be present prior to the execution

      resources:
        m1.large:
          control: 1
          network: 1
        m1.medium:
          compute: 10


Default provider configuration
------------------------------

The following options will be set automatically and thus may be omitted in the configuration file :

.. code-block:: yaml

    provider:
      type: chameleonkvm
      image_name: CC-Ubuntu16.04
      user: cc
      dns_nameservers: [129.114.97.1, 129.114.97.2, 129.116.84.203]
      network_interface: ens3

These options can be overriden in the provider config.
