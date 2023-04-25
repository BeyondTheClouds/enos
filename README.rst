|Doc Status| |Pypi| |Code style| |License|

Join us on gitter :  |Join the chat at
https://gitter.im/BeyondTheClouds/enos|

About Enos
==========

Enos aims at reproducible experiments of OpenStack.  Enos relies on
`Kolla Ansible <https://docs.openstack.org/kolla-ansible/>`__ and
helps you to easily deploy, customize and benchmark an OpenStack on
several testbeds including `Grid'5000 <https://www.grid5000.fr>`__,
`Chameleon <https://www.chameleoncloud.org/>`__ and more generally any
OpenStack cloud.

Installation
============

Enos is best installed via `pip <https://pip.pypa.io/>`__.  It is
tested with python3.7+::

  pip install enos

Quick Start
===========

For the quick-start, we will bring up an OpenStack on VirtualBox.
VirtualBox is free and works on all major platforms.  Enos can,
however, work with many testbeds including `Grid'5000
<https://beyondtheclouds.github.io/enos/provider/grid5000.html>`__ and
`Chameleon
<https://beyondtheclouds.github.io/enos/provider/openstack.html>`__.

First, make sure your development machine has `VirtualBox
<https://www.virtualbox.org/>`__ and `Vagrant
<https://www.vagrantup.com/downloads>`__ installed.  Then, ensure that
you have at least 10 GiB of memory.

To deploy your fist OpenStack with enos::

  enos new --provider=vagrant:virtualbox  # Generate a `reservation.yaml` file
  enos deploy

Enos starts three virtual machines and configures Kolla Ansible to
deploy the OpenStack control plane on the first one, the network
related services (Neutron, HAProxy, RabbitMQ) on the second one, and
use the last one as a compute node.  Note that the full deployment may
take a while (around 30 minutes to pull and run all OpenStack docker
images).

You can `customize
<https://beyondtheclouds.github.io/enos/customization/>`__ the
deployed services and the number of virtual machines allocated by
modifying the generated ``reservation.yaml`` file.  Calls ``enos
--help`` or read the `documentation
<https://beyondtheclouds.github.io/enos/>`__ for more information.

Acknowledgment
==============

Enos is developed in the context of the `Discovery
<https://beyondtheclouds.github.io/>`__ initiative.


Links
=====

-  Docs - https://beyondtheclouds.github.io/enos/
-  Discovery - https://beyondtheclouds.github.io/
-  Docker - https://hub.docker.com/r/beyondtheclouds/

.. |Join the chat at https://gitter.im/BeyondTheClouds/enos| image:: https://badges.gitter.im/BeyondTheClouds/enos.svg
   :target: https://gitter.im/BeyondTheClouds/enos?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. |Code style| image:: https://api.codacy.com/project/badge/Grade/87536e9c0f0d47e08d1b9e0950c9d14b
   :target: https://www.codacy.com/app/msimonin/enos?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=BeyondTheClouds/enos&amp;utm_campaign=Badge_Grade
.. |License| image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0
.. |Pypi| image:: https://badge.fury.io/py/enos.svg
    :target: https://badge.fury.io/py/enos
.. |Doc Status| image:: https://github.com/BeyondTheClouds/enos/actions/workflows/build-and-publish-doc.yml/badge.svg
   :target: https://github.com/BeyondTheClouds/enos/actions/workflows/build-and-publish-doc.yml
