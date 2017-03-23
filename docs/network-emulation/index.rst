Network Emulation
=================

Links description
-----------------

Enos allows to enforce network emulation in terms of latency and bandwidth
limitations. 

Network constraints (latency/bandwidth limitations) are enabled by the use of
groups of nodes. Resources *must* be described using a :code:`topology` description
instead of a :code:`resources` description. The following example will define 4 groups named :code:`grp1`, :code:`grp2`, :code:`grp3` and :code:`grp4`  respectively:

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

As a result 

* the network delay between every machines of :code:`grp1` and the machines of the other groups will be 20ms (2x10ms: symetric)
* the bandwidth between every machines of :code:`grp1` and the machines of the other groups will be 1 Gbit/s
* the network delay between every machines of :code:`grp2` and :code:`grp3` (resp. :code:`grp2` and :code:`grp4`) (resp. :code:`grp3` and :code:`grp4`) will be 50ms
* the bandwidth between every machines of :code:`grp2` and :code:`grp3` (resp. :code:`grp2` and :code:`grp4`) (resp. :code:`grp3` and :code:`grp4`) will be 100Mbit/s.

Checking the constraints
------------------------

Invoking

.. code-block:: bash

    python -m enos.enos tc --test

will generate various reports to validate the constraints. They are based on :code:`fping` and :code:`flent` latency and bandwidth measurements respectively. The reports will be located in the result directory.


Notes
-----

* To disable the network constraints you can specify :code:`enable: false` under the :code:`network_constraints` key and launch again :code:`python -m enos.enos tc`.
* To exclude a group from any tc rule, you can add an optionnal :code:`except` key to the :code:`network_constraints`: 

.. code-block:: yaml

    network_constraints:
      enable: true
      default_delay: 25ms
      default_rate: 100mbit
      constraints:
        - src: grp[1-3]
          dst: grp[4-6]
          delay: 10ms
          rate: 1gbit
          symetric: true
      except:
        - grp1


