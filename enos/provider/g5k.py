# -*- coding: utf-8 -*-
# from execo_g5k import api_utils as api
# from execo_g5k import OarSubmission
# from .host import Host
# from itertools import islice
# from netaddr import IPAddress, IPNetwork, IPSet
from provider import Provider
# from ..utils.extra import build_roles, get_total_wanted_machines 

import logging
from enos.utils.extra import gen_enoslib_roles
import enoslib.infra.enos_g5k.provider as enoslib_g5k
from enoslib.api import expand_groups

# import execo as EX
# import execo_g5k as EX5
# import logging
# import operator
# import pprint

logger = logging.getLogger(__name__)


def _build_enoslib_conf(conf):
    enoslib_conf = conf.get("provider", {})
    if enoslib_conf.get("resources") is not None:
        return enoslib_conf
    else:
        raise Exception("TODO: Not implemented yet")


class G5k(Provider):

    def init(self, conf, force_deploy=False):
        logging.info("G5K provider")
        resources = conf.get("resources", {})
        enoslib_conf = _build_enoslib_conf(conf)
        g5k = enoslib_g5k.G5k(enoslib_conf)
        roles, networks = g5k.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        logging.info("Destroying G5K deployment")
        enoslib_conf = _build_enoslib_conf(env['config'])
        g5k = enoslib_g5k.Enos_g5k(enoslib_conf)
        g5k.destroy()

    def default_config(self):
        return {
            'name': 'Enos',
            'walltime': '02:00:00',
            'env_name': 'debian9-x64-min',
            'reservation': False,
            'vlans': {'rennes': "{type='kavlan'}/vlan=1"},
            'role_distribution': ROLE_DISTRIBUTION_MODE_STRICT,
            'single_interface': False,
            'user': 'root'
        }

    def __str__(self):
        return 'G5k'
