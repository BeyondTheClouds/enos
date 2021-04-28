Benchmarks
==========

Benchmarks are run by Enos by the mean of a workload description. A workload is
a set of scenarios grouped by type.  A workload is launched with the following
command:

.. code-block:: bash

		(venv) $ enos bench --workload=workload

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

After running the workload, a backup of the environment can be done
through :code:`enos backup`.


Rally
-----

Enos supports natively Rally scenarios. Please refer to the Rally documentation
for any further information on this benchmarking tool.

Supported keys :

* :code:`name`: the name of the scenario. Can be any string.
* :code:`file`: must be the path to the scenario file. The path is relative to the
  :code:`workload` directory
* :code:`enabled`: Whether to run this scenario
* :code:`args`: Any parameters that can be understood by the rally scenario
* :code:`plugin`: must be the path to the plugin. The path is relative to the workload directory

Shaker
------

Enos supports natively Shaker scenarios. Please refer to the Shaker documentation
for any further information on this benchmarking tool.

Supported keys :

* :code:`name`: the name of the scenario. Can be any string.
* :code:`file`: must be the alias of the scenario. Enos don't support custom scenario
  yet.
* :code:`enabled`: Whether to run this scenario
