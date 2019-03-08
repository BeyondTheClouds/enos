.. _vmong5k:

Virtual Machines on Grid'5000
=============================

It is possible to deploy virtual machines on top of bare nodes of Grid'5000.
This hybrid approach is useful to take advantage of all resources available in
each node. In this way several virtual machines with different roles can be
coexist at the same time in a single node depending on the requirements.
Actually, in the current implementation machines with different roles will not
be colocalized (enoslib limitation) but several those with the same role can
coexist. The provisioning of the virtual machines and their deployment is
transparent to the user.


Basic configuration
-------------------

The ``vmong5k`` provider relies on cluster names to group wanted resources in
the same way the Grid'5000 provider does. It also take advantage of the virtual
machine sizes of the Vagrant provider to describe resources.

Refer to the :ref:`installation` section to install EnOS.

The following is a valid resource description:

.. literalinclude:: ../../tests/functionnal/tests/vmong5k/basic-00.yaml
   :language: yaml
   :linenos:


Deployment
----------

We suggest running the deployment from a dedicated node (specially for large
deployments). To reserve a node prior the deployment and launch the deployment
you can execute the commands after creating a valid configuration file and
setting up the appropriate execution environment for EnOS:

.. code-block:: bash

   frontend> oarsub -I -l 'walltime=2:00:00'
   node> enos deploy


Default Provider Configuration
------------------------------

The provider comes with the following default options:

.. literalinclude:: ../../enos/provider/vmong5k.py
   :language: python
   :start-after: # - SPHINX_DEFAULT_CONFIG
   :end-before: # + SPHINX_DEFAULT_CONFIG

These values be overridden in the configuration file.

.. note::

   Some default values are implicit. They are the defaults from the other
   providers involved in the deployment and execution.


Advanced Configurations
-----------------------

A configuration equivalent to the basic one presented before shows a finer and
more explicit definition of the resources:

.. literalinclude:: ../../tests/functionnal/tests/vmong5k/advanced-00.yaml
   :language: yaml
   :linenos:


Other possibilities includes the customization of the topology, networking, etc.
These options are described in :ref:`customizations` and
:ref:`network-emulation`.

.. note::

   The flavor of the resource can be set by name or using an inline description
   with ``flavour_desc`` as is the case of the network in the example.


Build an Image
--------------

A personalised image created and stored in Grid'5000, containing all the
dependencies to install OpenStack in subsequent deployments, may be built
directly from the command line on-the-fly without any intermediary deploy
execution. Run the command ``enos build vmong5k``, changing the default values
accordingly (specially the ``--cluster`` one).

In order to complete the image construction, after the execution of EnOS, a file
with the same name of the virtual machine created during the enactment (for
example:  ``vm-ac28907433b45227ee0d784d24ac91fb-1-0``) is located in the
directory configured with the argument ``--directory`` (default ``~/.enos``).
Rename this file and placed it in a permanent location visible on Grid'5000 such
as ``~/public/enos-openstack-image.qcow2``, then the configuration can reuse that
image setting the image as follows:

.. code-block:: bash

   provider:
     type: vmong5k
     image: ~/public/enos-openstack-image.qcow2
     ...
