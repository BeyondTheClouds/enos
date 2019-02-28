.. _vagrant-provider:

Vagrant
=======

Installation
------------

To get started with the vagrant provider, you need to install

* `Vagrant <https://www.vagrantup.com/>`_

You'll also need a virtualization backend. EnOS supports both Virtualbox and
Libvirt as shown below.

Then, refer to the :ref:`installation` section to install Enos.

Basic Configuration
-------------------

The provider relies on virtual machine sizes to group the wanted resources. For
example the following is a valid configuration

.. literalinclude:: ../../tests/functionnal/tests/vagrant/basic_vbox.yaml
   :language: yaml
   :linenos:

The list of the sizes may be found :enos_src:`here
<enos/provider/enos_vagrant.py#L12>`.

By default virtualbox will be used. See below to learn how to change the default
virtualbox backend.

Use libvirt as the backend for Vagrant
--------------------------------------

Declaring your provider options as the following will spin up virtual machines using libvirt.
Note that `vagrant libvirt <https://github.com/vagrant-libvirt/vagrant-libvirt>`_ must be installed on your system.

.. literalinclude:: ../../tests/functionnal/tests/vagrant/basic_libvirt.yaml
   :language: yaml
   :linenos:

Use the advanced syntax
------------------------

The following is equivalent to the basic configuration but allows for a finer
grained definition of the resources and associated roles.

.. literalinclude:: ../../tests/functionnal/tests/vagrant/advanced_2_nics_libvirt.yaml
   :language: yaml
   :linenos:

Default Configuration
---------------------

.. literalinclude:: ../../enos/provider/enos_vagrant.py
   :start-after: # - SPHINX_DEFAULT_CONFIG
   :end-before: # + SPHINX_DEFAULT_CONFIG

Build an Image
--------------

A reference image for Vagrant, containing all the dependencies to install
OpenStack in subsequent deployments, may be built directly from command line
on-the-fly without an intermediary deploy execution. Run the ``enos build``
command, changing the default values accordingly.

In order to complete the image construction, after the execution of EnOS execute
the following commands to register a box named ``personal/enos-box-openstack``:

.. code-block:: bash

   > vagrant package
   > vagrant box add package.box --name personal/enos-box-openstack


Once the box is registed in the vagrant catalog, the name of this box can be
used in the EnOS configuration replacing the default one. For example:

.. code-block:: yaml

   provider:
     type: vagrant
     backend: virtualbox
     box: personal/enos-box-openstack
     ...
