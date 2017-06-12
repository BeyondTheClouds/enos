.. _provider:

Provider
=========

Enos offers to test different OpenStack deployments over some
resources. In the context of Enos, a resource is anything Enos can SSH
on and start a Docker daemon. Thus, a resource could be a bare-metal
machine, a virtual machine, or a container resource depending on the
testbed used for conduction the experiments. To get these resources,
Enos relies on a notion of *provider* and already implements
the followings:

.. toctree::
   :maxdepth: 2

   static
   grid5000
   vagrant
   openstack
   custom
