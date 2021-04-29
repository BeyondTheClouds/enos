.. _contribute:

Contribute
==========

All contributions are welcome on `BeyondTheClouds/enos`_.
For any questions, feature requests, issues please use the `GitHub issue tracker`_.


.. _BeyondTheClouds/enos: https://github.com/BeyondTheClouds/enos
.. _GitHub issue tracker: https://github.com/BeyondTheClouds/enos/issues

Install from sources and make them editable
-------------------------------------------
Developing with enos requires `poetry`_.

.. code-block:: bash

    $ git clone https://github.com/BeyondTheClouds/enos.git
    $ cd enos
    $ poetry install

Then, execute enos from poetry.

.. code-block:: bash

    $ poetry run enos help
    $ poetry run enos deploy

.. _poetry: https://python-poetry.org/

Running the tests
-----------------

.. code-block:: bash

    $ poetry run tox

Running syntax checker
----------------------

.. code-block:: bash

    $ poetry run tox -e pep8

Generate the documentation
--------------------------

.. code-block:: bash

    $ poetry run tox -e docs


Other Topics
------------

.. toctree::
  :maxdepth: 1

  new-provider
