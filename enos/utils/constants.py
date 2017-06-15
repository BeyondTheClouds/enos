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
ANSIBLE_DIR = os.path.join(ENOS_PATH, 'ansible')

# NIC constants
NETWORK_IFACE = 0
EXTERNAL_IFACE = 1

# fake neutron external interface name
FAKE_NEUTRON_EXTERNAL_INTERFACE = 'fake_interface'

# ENOS Setup
VERSION = '3.0.0'
