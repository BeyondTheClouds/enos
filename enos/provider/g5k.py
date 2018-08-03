# -*- coding: utf-8 -*-
from execo_g5k import api_utils as api
from execo_g5k import OarSubmission
from .host import Host
from itertools import islice
from netaddr import IPAddress, IPNetwork, IPSet
from provider import Provider
from ..utils.extra import build_roles, get_total_wanted_machines

import execo as EX
import execo_g5k as EX5
import logging
import operator
import pprint


class G5k(Provider):
    def init(self, conf, force_deploy=False):
        raise Exception("TODO: Not implemented yet")

    def destroy(self, env):
        raise Exception("TODO: Not implemented yet")

    def default_config(self):
        return {
            'name': 'Enos',
            'walltime': '02:00:00',
            'env_name': 'jessie-x64-min',
            'reservation': False,
            'vlans': {'rennes': "{type='kavlan'}/vlan=1"},
            'role_distribution': ROLE_DISTRIBUTION_MODE_STRICT,
            'single_interface': False,
            'user': 'root'
        }

    def __str__(self):
        return 'G5k'
