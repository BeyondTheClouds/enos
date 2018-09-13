.. Enos documentation master file, created by
   sphinx-quickstart on Fri Jan 27 14:14:46 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Enos's documentation!
================================

.. hint ::

   The source code is available at
   https://github.com/BeyondTheClouds/enos

Enos deploys OpenStack and targets reproducible experiments. It allows easy:

* deployment of the system
* customization of the system
* benchmarking of the system
* visualization of various metrics

Enos is developed in the context of the
`Discovery <https://beyondtheclouds.github.io/>`_ initiative.

Enos workflow
-------------

A typical experiment using Enos is the sequence of several phases:

* :code:`enos up` : Enos will read the configuration file, get machines from
  the resource provider and will prepare the next phase
* :code:`enos os` : Enos will deploy OpenStack on the machines. This phase rely
  highly on Kolla deployment.
* :code:`enos init-os` : Enos will bootstrap the OpenStack installation (default
  quotas, security rules, ...)
* :code:`enos bench` : Enos will run a list of benchmarks. Enos support Rally
  and Shaker benchmarks.
* :code:`enos backup` : Enos will backup metrics gathered, logs and
  configuration files from the experiment.


.. toctree::
    :maxdepth: 2
    :caption: Contents:

    installation
    provider/index
    cli/index
    benchmarks/index
    customization/index
    network-emulation/index
    analysis/index
    contribute/index
    jenkins/index
    tutorial/index.rst

Why Enos ?
-----------

https://en.wikipedia.org/wiki/Enos_(chimpanzee)


License
-------

Enos runs performance stress workloads on OpenStack for postmortem analysis.
Copyright (C) 2016 Didier Iscovery

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.





Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
