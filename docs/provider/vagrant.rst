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
