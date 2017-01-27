Workload Injection
==================

A workload is a set of scenarios grouped by type.
A workload is launched with the following command:

.. code-block:: bash

		(venv)$ python -m enos.enos bench --workload=workload

enos will look into the :code:`workload` directory for a file named
:code:`run.yml`. This file is the description of the workload to launch.
One example is given below:

.. code-block:: yaml

    rally:
      enabled: true  # default is true
      args:
        concurrency:
          - 1
          - 2
          - 4
        times:
          - 100
      scenarios:
        - name: boot and list servers
          enabled: true # default is true
          file: nova-boot-list-cc.yml
          args:
          sla_max_avg_duration: 30
          times: 50

This will launch all the scenarios described under the scenarios keys with all
the possible parameters. The parameters are calculated using the cartesian
product of the parameters given under the args keys. Locally defined args
(scenario level) shadow globally defined args (top level). The same mechanism is
applied to the :code:`enabled` values.  The scenario must be parameterized
accordingly. The key (rally here) defines the type of benchmark to launch: in
the future we may support other type of scenarios.

After running the workload, a backup of the environment can be done through
:code:`python -m enos.enos backup`.

Notes
"""""

* The Rally scenario files must reside in the workload directory and will be
  uploaded during the process. Additionnaly they must be properly templatized.

* The Shaker scenario must correspond to the alias name of a predefined shaker
  scenario

