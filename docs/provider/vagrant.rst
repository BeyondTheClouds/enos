.. _vagrant-provider:

Vagrant
=======

Installation
------------

To get started with the vagrant provider, you need to install

* `Vagrant <https://www.vagrantup.com/>`_

Then, refer to the :ref:`installation` section to install Enos.

Configuration
-------------

The provider relies on virtual machine sizes to group the wanted resources. For
example the following is a valid resources description:


.. code-block:: yaml

    provider: vagrant

    resources:
      medium:
        control: 1
        network: 1
      small:
        compute:1

The list of the sizes may be found :enos_src:`here
<enos/provider/enos_vagrant.py#L12>`.

By default virtualbox will be used. See below to learn how to change the default
virtualbox backend.

Use libvirt as the backend for Vagrant
--------------------------------------

Declaring your provider options as the following will spin up virtual machines using libvirt.
Note that `vagrant libvirt <https://github.com/vagrant-libvirt/vagrant-libvirt>`_ must be installed on your system.

.. code-block:: bash

    provider:
      type: vagrant
      backend: libvirt

Default provider configuration
-------------------------------

The provider comes with the following default options:

.. code-block:: yaml

    provider:
      type: vagrant
      backend: virtualbox
      box: debian/jessie64
      user: root

They can be overriden in the configuration file.

A note on KVM
-------------

KVM is not supported in Vagrant when using VirtualBox.
To manually set qemu as hypervisor, the ``reservation.yaml`` has to be modified.
To tell kolla that a custom config will be used, patch the ``reservation.yaml`` with the following command: ``node_custom_config: "{{cwd}}/patch"``, in the kolla parameters (``{{cwd}}`` is the working directory of Enos).

For example in ``reservation.yaml``:  

.. code-block:: yaml

    kolla:
     [...]
     node_custom_config: "{{cwd}}/patch"

Then in ``{{cwd}}/patch``, create a file ``nova.conf`` that will overloads the default one, and add:

.. code-block:: ini

    [libvirt]
     virt_type=qemu

