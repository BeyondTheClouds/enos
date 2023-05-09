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


Release a new version
---------------------

As a pre-requisite, you will have to generate a token on pypi and configure poetry to use it:

.. code-block:: bash

    $ poetry config pypi-token.pypi XXXXXXX

Before making a new release, make sure that tests and pep8 are happy, and write
some appropriate changelog entries.

First, update the version in ``enos/utils/constants.py`` and ``pyproject.toml``.

Then, git tag, build a wheel with poetry, and upload it to pypi:

.. code-block:: bash

    $ git tag v8.0.0a2
    $ poetry build
    $ poetry publish
    $ git push --tags

Finally, create a release on github and copy-paste the changelog entries.

Other Topics
------------

.. toctree::
  :maxdepth: 1

  new-provider
