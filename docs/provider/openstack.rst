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

In addition refer to :ref:`installation`, extra dependencies are required. You
can install them with

.. code-block:: bash

    pip install enos[openstack]

Basic Configuration
-------------------

The provider relies on flavor names to group the wanted resources. The
folliwing gives an idea of the resource description available.

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

.. literalinclude:: ../../enos/provider/openstack.py
   :start-after: # - SPHINX_DEFAULT_CONFIG
   :end-before: # + SPHINX_DEFAULT_CONFIG

These options can be overriden in the provider config.


Deployment
----------

Enos will interact with the remote OpenStack APIs. In order to get authenticated
you must source your rc file. To use Enos on Openstack there are two distinct
cases :

* You have direct access to all your machines. You can set :code:`gateway: False`

.. hint::

    In this case, prior to the Enos deployment, you have probably started a
    machine to act as a frontend. This machine is in the same network as those
    used by Enos

* You don't have direct access to all your machines. You have to set
  :code:`gateway: True` in the configuration. EnOS will use a freshly started
  server as a gateway to access the other nodes.


Chameleon Cloud (KVM)
=====================

This provider is an OpenStack based provider where some options are set to fit
the folllowing platform :

* https://openstack.tacc.chameleoncloud.org

Basic Configuration
-------------------

As more default values can be enforced automatically, the following is a valid
resources description.

.. literalinclude:: ../../tests/functionnal/tests/chameleon/chameleonkvm-basic-00.yaml
   :language: yaml
   :linenos:

Default provider configuration
------------------------------

The following options will be set automatically and thus may be omitted in the configuration file :

.. literalinclude:: ../../enos/provider/chameleonkvm.py
   :start-after: # - SPHINX_DEFAULT_CONFIG
   :end-before: # + SPHINX_DEFAULT_CONFIG

These options can be overriden in the provider config.


Chameleon Cloud (Bare Metal)
=============================

This provider is an OpenStack based provider where some options are set to fit the following platforms :

* https://chi.uc.chameleoncloud.org/
* https://chi.tacc.chameleoncloud.org/


The provider interacts with blazar to claim automatically a lease.

Basic Configuration
-------------------

.. literalinclude:: ../../tests/functionnal/tests/chameleon/chameleonbaremetal-basic-00.yaml
   :language: yaml
   :linenos:


Note that on Chameleon, they are two groups of machines : compute and storage.

Default provider configuration
------------------------------

The following options will be set automatically and thus may be omitted in the
configuration file.


.. literalinclude:: ../../enos/provider/chameleonbaremetal.py
   :start-after: # - SPHINX_DEFAULT_CONFIG
   :end-before: # + SPHINX_DEFAULT_CONFIG

These options can be overriden in the provider config.


.. warning ::

    A shared-network is used and may limit the features of the over-cloud (e.g floating ips)
