.. _contribute:

Contribute
==========

All contributions are welcome on `BeyondTheClouds/enos`_.
For any questions, feature requests, issues please use the `GitHub issue tracker`_.


.. _BeyondTheClouds/enos: https://github.com/BeyondTheClouds/enos
.. _GitHub issue tracker: https://github.com/BeyondTheClouds/enos/issues

Install from sources and make them editable
-------------------------------------------

.. code-block:: bash

    $ git clone https://github.com/BeyondTheClouds/enos.git
    $ cd enos
    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install -e .


Get tox
-------

.. code-block:: bash

    (venv) $ pip install tox

Running the tests
-----------------

.. code-block:: bash

    (venv) $ tox

Running syntax checker
----------------------

.. code-block:: bash

    (venv) $ tox -e pep8

Generate the documentation
--------------------------

.. code-block:: bash

    (venv) $ tox -e docs


Other Topics
------------

.. toctree::
  :maxdepth: 1

  new-provider
