.. _installation:

Getting Started
================

Installation
------------

.. code-block:: bash

    $ pip install enos

You may prefer to go with a virtualenv. Please refer to the
`virtualenv <https://virtualenv.pypa.io/en/stable/>`_ documentation
and the rest of this section for further information.


If virtualenv is missing:

.. code-block:: bash

    $ pip install virtualenv --user     # Install virtualenv
    $ export PATH=~/.local/bin/:${PATH} # Put it into your path

Then install enos inside a virtualenv:

.. code-block:: bash

    $ mkdir my-experiment && cd my-experiment
    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install enos


.. note::

   The latest *packaged* version of enos will install the latest
   *stable* version of OpenStack. If you want to install the
   development version of OpenStack, you should install enos from
   sources (see :ref:`contribute`).


Configuration
-------------

To get started you can get the sample configuration file and edit it:

.. code-block:: bash

    $ curl https://raw.githubusercontent.com/BeyondTheClouds/enos/master/reservation.yaml.sample --output reservation.yaml
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
