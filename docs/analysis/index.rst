Analysis
========

Real-time
---------

Setting ``enable_monitoring: true`` in the configuration file will deploy a monitoring stack composed of:

* Cadvisor and Collectd agents
* InfluxDB for metrics collection
* Graphana for the visualization / exploration

All these services are accessible on their default ports.
For instance you'll be able to access grafana dashboards on port ``3000`` of the node hosting grafana.

Some dashboards are available in this `grafana directory <https://github.com/BeyondTheClouds/kolla-g5k-results/tree/master/files/grafana>`_.

Post-mortem
-----------

TODO

Annotations
-----------

Enos embeds an Ansible plugin to add annotations in Grafana.
These annotations are marked points which provide rich information about events
when hovered over.
Enos uses the ``ansible.cfg`` file that loads the plugin. The plugin can be
disabled by editing the line ``callback_whitelist = influxdb_events`` in the
``ansible.cfg``. Note also that the plugin is automaticaly disabled when
the monitoring tools are not deployed (i.e. when `enable_monitoring = false`
is set in the configuration file).

Once the deployment is finished, a compatible dashboard must be used in Grafana
to display annotations. An example of such dashboard is available `here
<https://github.com/BeyondTheClouds/kolla-g5k-results/blob/master/files/grafana/dashboard_annotations.json>`_.
