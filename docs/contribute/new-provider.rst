.. _new-provider:

Write a new provider
====================

The actual implementation gives providers for :ref:`static` resources,
:ref:`vagrant-provider`, :ref:`grid5000` and :ref:`openstack` itself. If
you want to support another testbed, then implementing a new provider
is easy as 500 lines of Python code.

The new provider should follow the :enos_src:`provider.py
<enos/provider/provider.py>` interface which consists in three
methods: ``init``, ``destroy`` and ``default_config``. Another good
starting point is the simple :enos_src:`static implementation
<enos/provider/static.py>`.


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

At the end of the ``init``, the provider should return a list of
:enos_src:`host.py <enos/provider/host.py>` that Enos can SSH on,
together with a pool of available IP for OpenStack Network.


Destroy Method
--------------

The ``destoy`` method destroys resources that have been used for the
deployment. The provider can rely on the environment variable to get
information related to its deployment.

Default Provider Configuration Methods
--------------------------------------

The ``default_config`` specifies keys used to configure the provider
with a ``dict``. A key could be *optional* and so should be provided
with a default value, or *required* and so should be set to ``None``.
The user then can override these keys in the reservation file, under
the ``provider`` key. Keys marked as ``None`` in the
``default_config`` are automatically tested for overriding in the
reservation file.

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
``config['provider']['extra-var']``. Supported extra information is
documented into the provider documentation.
