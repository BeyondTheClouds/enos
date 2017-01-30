Network Emulation
=================

Links description
-----------------

Enos allows to enforce network emulation in terms of latency and bandwidth
limitations. 

Network constraints (latency/bandwidth limitations) are enabled by the use of
groups of nodes. Resources *must* be described using a :code:`topology` description
instead of a :code:`resources` description. The following example will define 2 groups named :code:`grp1` and :code:`grp2` respectively :

.. code-block:: yaml

    topology:
      grp1:
        paravance:
          control: 1
          network: 1
      grp[2-4]:
        paravance:
          compute: 1

Constraints are then described under the :code:`network_constraints` key in
the configuration file:


.. code-block:: yaml

    network_constraints:
      enable: true
      default_delay: 25ms
      default_rate: 100mbit
      constraints:
        - src: grp1
          dst: grp[2-4]
          delay: 10ms
          rate: 1gbit
          symetric: true


To enforce the constraints, you can invoke:

.. code-block:: bash

    python -m enos.enos tc

Note that The machines must be available, thus the `up` phase must have been called before.

Checking the constraints
------------------------

Invoking

.. code-block:: bash

    python -m enos.enos tc --test

will generate various reports to validate the constraints. They are based on :code:`fping` and :code:`flent` latency and bandwidth measurement respectively. The reports will be located in the result directory.


Notes
-----

* To disable the network constraints you can specify :code:`enable: false` under the :code:`network_constraints` key and launch again :code:`python -m enos.enos tc`.
