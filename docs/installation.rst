.. _installation:

Getting Started
================

Installation
------------

.. code-block:: bash

    $ git clone https://github.com/BeyondTheClouds/enos

You should also choose to go with a virtualenv. Please refer to the `virtualenv
<https://virtualenv.pypa.io/en/stable/>`_ documentation for further information.



If virtualenv is missing:

.. code-block:: bash

    $ pip install virtualenv --user # Install virtualenv
    $ export PATH=~/.local/bin/:${PATH} # Put it into your path

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

    python -m enos.enos deploy
