.. _openstacksdk:

=============
OpenStack SDK
=============
The python `OpenStack SDK <https://docs.openstack.org/openstacksdk/latest/index.html>`_
is a library that exposed the OpenStack API to the developers. The
following use information provided by Enos to connect to OpenStack 
and then programmatically create a project, users and networks. It
assumes Enos has already deployed an OpenStack and your are in the
virtual environment if you have created one.

First install the OpenStack SDK.

.. code-block:: sh

  (venv) $ pip install python-openstacksdk

Then asks enos where is your ``admin-openrc``, source it and check 
everything is OK.

.. code-block:: sh

  (venv) $ source $(enos info --out json|jq -r '.resultdir')/admin-openrc
  (vnev) $ env|fgrep OS|sort
  OS_AUTH_PLUGIN=password
  OS_AUTH_URL=http://10.24.189.255:35357/v3
  OS_IDENTITY_API_VERSION=3
  OS_INTERFACE=internal
  OS_PASSWORD=demo
  OS_PROJECT_DOMAIN_NAME=Default
  OS_PROJECT_NAME=admin
  OS_REGION_NAME=RegionOne
  OS_TENANT_NAME=admin
  OS_USER_DOMAIN_NAME=Default
  OS_USERNAME=admin

And that's it! 

Now, you can execute the following ``openstacksdk.py`` file that reads 
``OS_*`` variables from you environment to instantiate the ``cloud`` 
REST client. Executes it with ``python openstacksdk.py``.

.. literalinclude:: openstacksdk.py
  :language: python

