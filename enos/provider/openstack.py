# NOTE(msimonin): we should get rid of this
from ..utils.extra import (build_roles,
                           get_total_wanted_machines,
                           gen_resources)
from .host import Host
from glanceclient import client as glance
from keystoneauth1.identity import v2
from keystoneauth1 import session
from neutronclient.neutron import client as neutron
from novaclient import client as nova
from operator import itemgetter
from provider import Provider

import ipaddress
import logging
import os
import re
import time


class Openstack(Provider):
    def init(self, conf, force_deploy=False):
        raise Exception("TODO: not implemented yet")

    def default_config(self):
        raise Exception("TODO: not implemented yet")

    def destroy(self, env):
        raise Exception("TODO: not implemented yet")
