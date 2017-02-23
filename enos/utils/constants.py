# -*- coding: utf-8 -
import os

# PATH constants
ENOS_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SYMLINK_NAME = os.path.join(os.getcwd(), 'current')
TEMPLATE_DIR = os.path.join(ENOS_PATH, 'templates')
ANSIBLE_DIR = os.path.join(ENOS_PATH, 'ansible')

# NIC constants
NETWORK_IFACE = 0
EXTERNAL_IFACE = 1

# ENOS Setup
VERSION = '1.0.1'
