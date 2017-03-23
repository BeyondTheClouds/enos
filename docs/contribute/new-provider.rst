.. _new-provider:

Write a new provider
====================

The actual implementation gives two providers: :ref:`grid5000` and
:ref:`vagrant-provider`. If you want to support another testbed, 
then implementing a new one is easy as 500 lines of Python code.

The new provider should follow the `provider.py`_ interface which
consists in four methods: ``init``, ``destroy``, ``before_preintsall``
and ``after_preinstall``.

.. _provider.py: https://github.com/BeyondTheClouds/enos/blob/master/enos/provider/provider.py

Init Method
-----------

The ``init`` method provides resources and provisions the environment.
To let the provider knows what kind and how many resources should be
provided, the method is fed with the ``config`` object that maps the
reservations file. So a provider can access the resource description
with:

.. code-block:: python

   rsc = config['resources']

   # Use rsc to book resources ...

At the end of the ``init``, the provider should return a list of hosts
that Enos can SSH on, together with a pool of available IP for
OpenStack Network.

Destroy Method
--------------

The ``destoy`` method destroys resources that have been used for the
deployment. The provider can rely on the environment variable to get
information related to its deployment.

Before and After Preinstall Methods
-----------------------------------

During its up phase, Enos calls a provider to get resources and then
provisions them with docker and other util tools. The provider can use
theses two methods to perform extra actions before and after the
provisioning.

Provider Instantiation
----------------------

Enos automatically instantiates a provider based on the name specified
in the ``reservation.yaml``. For instance, based on the following
reservation file,

.. code-block:: yaml

   provider: "my-provider"

Enos seeks for a file called ``my-provider.py`` into ``enos/provider``
and instantiates its main class. But sometimes, the provider requires
extra information for its initialisation. The good place for this
information is to put it under the provider key. In this case, the
provider name should be accessible throughout the ``type`` key:

.. code-block:: yaml

   provider:
     type: "my-provider"
     extra-var: ...
     ...

Then the provider can access ``extra-var`` with
``config['provider']['extra-var']``. Supported extra information
should be well documented into the provider documentation.
