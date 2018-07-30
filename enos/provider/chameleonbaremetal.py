from blazarclient import client as blazar_client
from keystoneclient import client as keystone
from neutronclient.neutron import client as neutron

import chameleonkvm as cc
import datetime
import logging
import openstack
import os
import time

PORT_NAME = "enos-port"

class Chameleonbaremetal(cc.Chameleonkvm):
    def init(self, conf, force_deploy=False):
        raise Exception("TODO, not implemented yet")

    def destroy(self, env):
        raise Exception("TODO, not implemented yet")
        # destroy the associated lease should be enough

    def default_config(self):
        raise Exception("TODO, not implemented yet")
