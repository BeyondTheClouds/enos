Analysis
========

Real-time
---------

Setting ``enable_monitoring: true`` in the configuration file will deploy a monitoring stack composed of :

* Cadvisor and Collectd agents
* InfluxDB for metrics collection
* Graphana for the visualization / exploration

All these services are accessible on their default ports.
For instance you'll be able to access grafana dashboards on port ``3000`` of the node hosting grafana.

Some dashboards are available `here <https://github.com/BeyondTheClouds/kolla-g5k-results/tree/master/files/grafana>`_

Post-mortem
-----------

TODO
