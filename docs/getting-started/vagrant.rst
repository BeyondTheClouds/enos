.. _vagrant-provider:

Vagrant
=======

Installation
------------

Vagrant setup
^^^^^^^^^^^^^

To get started with the vagrant provider, you need to install

* `Vagrant <https://www.vagrantup.com/>`_

Code setup
^^^^^^^^^^

To install Enos, clone the repository:

.. code-block:: bash

    $ git clone https://github.com/BeyondTheClouds/enos

You should also choose to go with a virtualenv. Please refer to the `virtualenv
<https://virtualenv.pypa.io/en/stable/>`_ documentation for further information.

Then install the dependencies:

.. code-block:: bash

    $ cd enos
    $ virtualenv venv
    $ source venv/bin/activate
    (venv)$ pip install -r requirements.txt


Configuration
-------------

To get started you can copy the sample configuration file and edit the resulting
file:

.. code-block:: bash

    $ cp reservation.yaml.sample reservation.yaml
    $ <editor> reservation.yaml

The provider relies on virtual machine sizes instead of cluster names. For
example the following is a valid resources description:


.. code-block:: bash

    provider: vagrant

    resources:
      medium:
        control: 1
        network: 1
      small:
        compute:1

The list of the sizes may be found `here
<https://github.com/BeyondTheClouds/enos/blob/master/enos/provider/enos_vagrant.py#L12>`_.

By default virtualbox will be used. See below to learn how to change the default
virtualbox backend.

Deployment
-----------

To launch the deployment, run:

.. code-block:: bash

    python -m enos.enos deploy

Use libvirt as the backend for Vagrant
--------------------------------------

Declaring your provider option as the following will spin up virtual machines using libvirt.
Note that `vagrant libvirt <https://github.com/vagrant-libvirt/vagrant-libvirt>`_ must be installed on your system.

.. code-block:: bash

    provider:
      type: vagrant
      backend: libvirt

Default provider configuration
-------------------------------

The provider comes with the following default options :

.. code-block:: javascript

    DEFAULT_PROVIDER_CONFIG = {
        'backend': 'virtualbox',
        'box': 'debian/jessie64',
        'user': 'root',
        'interfaces': ('eth1', 'eth2')
    }
