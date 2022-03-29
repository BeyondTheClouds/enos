.. _installation:

Getting Started
================

.. note::

   Looking for a step-by-step tutorial?  We have a :ref:`full
   tutorial<grid5000-tuto>` explaining how to run Enos
   on the `Grid'5000 platform <https://www.grid5000.fr>`_.

Installation
------------

.. code-block:: bash

    $ pip install -U enos

You may prefer to go with a virtualenv. Please refer to the
`virtualenv <https://virtualenv.pypa.io/en/stable/>`_ documentation
and the rest of this section for further information.


Then install enos inside a virtualenv (python3.7+ required):

.. code-block:: bash

    $ mkdir my-experiment && cd my-experiment
    $ virtualenv -p python3 venv
    $ source venv/bin/activate
    (venv) $ pip install -U pip
    (venv) $ pip install enos


.. note::

   The latest *packaged* version of enos will install the latest
   *stable* version of OpenStack.


Configuration
-------------

To get started you need an Enos configuration file.  Among other
things, that file tells Enos on which testbed to acquire resources and
deploy OpenStack.  Enos supports many testbeds including Vagrant,
Grid'5000, Chameleon and more generally any OpenStack cloud.

The configuration may vary from one testbed to another.  For this
quick-start, we will bring up an OpenStack on Vagrant/VirtualBox
because it is free and works on all major platforms.  Please, refer to
the dedicated :ref:`provider` section for the full list of supported
testbed.

First, make sure you have `VirtualBox <https://www.virtualbox.org/>`__
and `Vagrant <https://www.vagrantup.com/downloads>`__ installed. Then,
generate the configuration file with:

.. parsed-literal::

    (venv) $ enos new --provider=vagrant:virtualbox

This generates a ``reservation.yaml`` file in the current directory.
This file shows available configuration options (and their defaults in
comments).  Take the time to review that file before going further.

.. note::

    If a key is defined several times in the configuration file, only the last
    occurence will be taken into account. In particular to switch from one
    provider to another, you can move down the key ``provider`` and its
    associated ``resources`` key.

Deployment
----------

Once your configuration is done, you can launch the deployment:

.. code-block:: bash

    (venv) $ enos deploy

The deployment is the combination of the following three phases:

1. Acquire the resources that are necessary for the deployment of
   OpenStack. Enos acquires resources according to the ``provider``
   and ``resources`` information in the configuration file. One can
   perform this phase by calling ``enos up``.

2. Deploy OpenStack on the resources acquired during the previous
   phase. Enos uses the resource list provided by the previous phase
   and combines it with the information specified in the file targeted
   by the ``inventory`` key to produce a file that gives a mapping of
   which OpenStack services have to be deployed to which resources.
   Enos then calls the Kolla Ansible tool with this file to deploy the
   containerized OpenStack services to the right resources. One can
   perform this phase by calling ``enos os``.

   .. note::

      If you don't provide an ``inventory`` in your current working
      directory, then Enos uses a default one. You can view it on
      GitHub at :enos_src:`enos/resources/inventory.sample`. Note
      that the produced file is available at ``cwd/current/multinode``
      (with ``cwd`` referencing to your current working directory).

   .. warning::

      If you run Enos on macOS, chances are that the BSD version of `docopt`
      has been installed. Since it is not compatible with Kolla-Ansible,
      it leads to failures during the second phase of Enos. macOS users
      should first install the GNU version of `docopt`, and call ``enos
      deploy`` or ``enos os`` with an appropriate PATH environment variable:

      .. code-block:: bash

         (venv) $ brew install gnu-docopt
         (venv) $ PATH="/usr/local/opt/gnu-getopt/bin:$PATH" enos deploy

3. Initialize the freshly deployed OpenStack. Enos initializes
   OpenStack with the bare necessities, i.e., install a ``member``
   role, download and install a cirros image, install default flavors
   (m1.tiny, ..., m1.xlarge) and setup a network (one public/one
   private). One can perform this phase by calling ``enos init``.
