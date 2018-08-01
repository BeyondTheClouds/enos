# -*- coding: utf-8 -*-
import logging

import enoslib.infra.enos_g5k.provider as enoslib_g5k

from enos.utils.extra import gen_enoslib_roles
from enoslib.api import expand_groups
from provider import Provider


logger = logging.getLogger(__name__)


DEFAULT_NETWORKS = [
    {
        "id": "int-net",
        "site": "rennes",
        "type": "kavlan",
        "role": "network_interface"
    },
    {
        "id": "ext-net",
        "site": "rennes",
        "type": "kavlan",
        "role": "neutron_network_interface"
    }]


def _build_enoslib_conf(conf):
    # """
    # >>> config = { \
    #         "resources": { \
    #              "parapluie": { \
    #                  "compute": 3, \
    #                  "network": 1, \
    #                  "control": 1  } } }
    # >>> _build_enoslib_conf(config)
    # """
    enoslib_conf = conf.get("provider", {})
    if enoslib_conf.get("resources") is not None:

        # enoslib mode
        logging.debug("Getting resources specific to the provider")
        return enoslib_conf

    # EnOS legacy mode
    logging.debug("Getting generic resources from configuration")
    machines = []

    # get a plain configuration of resources
    resources = conf.get("resources", {})
    single_interface = conf.get("single_interface", "no")

    # when an advanced configuration is present (aka topology)
    # replace resources with that configuration
    resources = conf.get("topology", resources)
    for desc in gen_enoslib_roles(resources):
        groups = expand_groups(desc["group"])
        for group in groups:
            machine = {"roles": [group, desc["role"]],
                       "number": desc["number"],
                       "cluster": desc["flavor"],
                       "primary_network": "int-net"}

            # add secondary network only if single interface is not set
            if single_interface == "no":
                machine.update({"secondary_networks": ["ext-net"]})

            machines.append(machine)

    enoslib_conf.update({"resources":
                         {"machines": machines,
                          "networks": DEFAULT_NETWORKS}})

    return enoslib_conf


class G5k(Provider):

    def init(self, conf, force_deploy=False):
        logging.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(conf)
        logging.debug("Creating G5K provider")
        g5k = enoslib_g5k.G5k(enoslib_conf)
        logging.info("Initializing G5K provider")
        roles, networks = g5k.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        conf = env.get('config')
        logging.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(conf)
        logging.debug("Creating G5K provider")
        g5k = enoslib_g5k.Enos_g5k(enoslib_conf)
        logging.info("Destroying G5K deployment")
        g5k.destroy()

    def default_config(self):
        return {'job_name': 'Enos',
                'walltime': '02:00:00',
                'env_name': 'debian9-x64-min',
                'reservation': False,
                'role_distribution': ROLE_DISTRIBUTION_MODE_STRICT,
                'single_interface': False,
                'user': 'root'}

    def __str__(self):
        return 'G5k'
