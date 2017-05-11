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

# Number of time we'll be retrying an ssh connection
# to the machines after the provider init call.
SSH_RETRIES = 100
# Interval to wait in seconds between two retries
SSH_RETRY_INTERVAL = 30

# ENOS Setup
VERSION = '2.0.0'
