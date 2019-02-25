.. _installation:

Getting Started
================

Installation
------------

.. code-block:: bash

    $ pip install -U enos

You may prefer to go with a virtualenv. Please refer to the
`virtualenv <https://virtualenv.pypa.io/en/stable/>`_ documentation
and the rest of this section for further information.


Then install enos inside a virtualenv (python3.5+ required):

.. code-block:: bash

    $ mkdir my-experiment && cd my-experiment
    $ virtualenv -p python3 venv
    $ source venv/bin/activate
    (venv) $ pip install -U pip
    (venv) $ pip install enos


.. note::

   The latest *packaged* version of enos will install the latest
   *stable* version of OpenStack. If you want to install the
   development version of OpenStack, you should install enos from
   sources (see :ref:`contribute`).


Configuration
-------------

To get started you can get the sample configuration file and edit it:

.. parsed-literal::

    $ enos new > reservation.yaml
    $ <editor> reservation.yaml


The configuration may vary from one provider to another, please refer to the
dedicated :ref:`provider` configuration


.. note::

    If a key is defined several times in the configuration file, only the last
    occurence will be taken into account. In particular to switch from one
    provider to another, you can move down the key ``provider`` and its
    associated ``resources`` key.

Deployment
----------

Once your configuration is done, you can launch the deployment :

.. code-block:: bash

    (venv) $ enos deploy


The deployment is the combination of the following three phases:

1. Acquire the raw resources that are necessary for the deployment of
   OpenStack. Enos acquires resources according to the ``provider``
   and ``resources`` information in the reservation file. One can
   perform this phase by calling ``enos up``.

2. Deploy OpenStack to the resources acquired during the previous
   phase. Enos uses the resource list provided by the previous phase
   and combines it with the information specified in the file targeted
   by the ``inventory`` key to produce a file that gives a mapping of
   which OpenStack services have to be deployed to which resources.
   Enos then calls the Kolla-Ansible tool with this file to deploy the
   containerized OpenStack services to the right resources. One
   can perform this phase by calling ``enos os``.

   .. note::

      If you don't provide an ``inventory`` in your current working
      directory, then Enos uses a default one. You can view it on
      GitHub at :enos_src:`enos/inventories/inventory.sample`. Note
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
