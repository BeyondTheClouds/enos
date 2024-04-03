.. _releasenotes:

Release notes
=============

.. _v8.0.0:

8.0.0 (2024-04-03)
------------------

- **Breaking change:** the format of ``enos info`` has changed
- Install a fixed version of Docker on nodes
- Add support for kolla-ansible 12 (Openstack Wallaby), which is now the default
- Add support for Debian 11 base image
- Add support for Python 3.10 and 3.11
- Drop support for Python 3.7
- Update to Enoslib 8
- When creating a configuration template, use a fixed version of kolla-ansible (so that templates are not affected when future versions of Enos update the default version of kolla-ansible)

.. _v7.1.1:

7.1.1 (2022-03-30)
------------------

- Fix Docker registry mirror configuration
- Pin Jinja2 version to avoid breaking kolla-ansible filters
- Update Grid'5000 tutorial

.. _v7.1.0:

7.1.0 (2021-06-02)
------------------

- Modularization of tasks. Task can now be imported in another python project to build upon enos.
- Enhance the cli with new error messages and colors.
- Lazy load enoslib to speed up the print of help messages.

Older releases
--------------

See https://github.com/BeyondTheClouds/enos/releases
