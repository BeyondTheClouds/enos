# -*- coding: utf-8 -

# Note: Never import dependencies to the rest of enos here: this will
# put a mess during the packaging. `setup.py` imports this file to get
# enos version. So importing the rest of enos here will evaluate the
# rest of enos and obviously enos needs dependencies that won't be
# installed yet.

import os

# PATH constants
ENOS_PATH = os.path.abspath(
  os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SYMLINK_NAME = os.path.abspath(os.path.join(os.getcwd(), 'current'))
TEMPLATE_DIR = os.path.join(ENOS_PATH, 'templates')
INVENTORY_DIR = os.path.join(ENOS_PATH, 'inventories')
ANSIBLE_DIR = os.path.join(ENOS_PATH, 'ansible')
VENV_KOLLA = 'venv_kolla'

# KOLLA_NETWORKS (some of them)
#
# Référence: https://docs.openstack.org/kolla-ansible
# production-architecture-guide.html#network-configuration
#
# Default interface used by kolla to handle all the openstack traffic. It will
# be provisionned automatically on the first NIC available. Finer grained
# configuration using other network roles is possible using the enoslib
# description.
NETWORK_INTERFACE = 'network_interface'

# Network used by the APIs.
# We used it if defined to get virtual ips (haproxy) from.
API_INTERFACE = 'api_interface'

# Interface used for external access (e.g vm -> internet).
# We choose to rely on a dedicated interface to manage external traffic. Having
# all the traffic go through a single interface is possible but the network
# connection may break at deployment time (when neutron creates the wiring to
# the external bridge). If two NICs are available the second one must be used
# for this interface. If only one nic is available the framework will create a
# fake interface a give it the neutron_external_interface role
NEUTRON_EXTERNAL_INTERFACE = 'neutron_external_interface'

# In case we need to create a fake interface, this will be the nic name.
FAKE_NEUTRON_EXTERNAL_INTERFACE = 'nei'

# ENOS Setup
VERSION = '4.1.2'
