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

Some dashboards are available `here <https://github.com/BeyondTheClouds/kolla-g5k-results/tree/master/files/grafana>`_.

Post-mortem
-----------

TODO

Annotations
-----------

Enos embeds an Ansible plugin to add annotations in Grafana's graphs.
These annotations are marked points which provide rich information about events
when hovered over. To enable this option, the plugin must be loaded and the
monitoring stack must be deployed (i.e. ``enable_monitoring: true`` should be
set in the configuration file).

To enable the plugin, the ``ANSIBLE_CONFIG`` environment variable should be set
to an ``ansible.cfg`` which loads the plugin. To that end, Enos can be called
this way: ``ANSIBLE_CONFIG="./enos/ansible.cfg" python -m enos.enos deploy``,
or you can export the variable for more convenience (more information about
``ansible.cfg`` can be found `here
<http://docs.ansible.com/ansible/intro_configuration.html>`_).

Then, a compatible dashboard must be used in Grafana to display
annotations. An example of such dashboard is available `here
<https://github.com/BeyondTheClouds/kolla-g5k-results/blob/master/files/grafana/dashboard_annotations.json>`_.

