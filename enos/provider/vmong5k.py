import copy
import logging

from enoslib import api
from enoslib.infra.enos_vmong5k.configuration import Configuration
from enoslib.infra.enos_vmong5k.provider import VMonG5k as VMonG5K

from . import g5k
from .provider import Provider
from ..utils import constants
from ..utils import extra

LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'job_name': 'enos-vmong5k',
    'walltime': '02:00:00'
}


def _build_enoslib_configuration(configuration):
    _configuration = copy.deepcopy(configuration)
    enoslib_configuration = _configuration.get("provider", {})
    enoslib_configuration.pop("type", None)
    if enoslib_configuration.get("resources") is not None:
        return enoslib_configuration

    machines = []
    clusters = set()
    resources = _configuration.get("resources", {})
    resources = _configuration.get("topology", resources)
    for description in extra.gen_enoslib_roles(resources):
        for group in api.expand_groups(description["group"]):
            clusters.add(description["flavor"])
            machine = {
                "roles": [group, description["role"]],
                "nodes": description["number"],
                "cluster": description["flavor"],
                "min": 1
            }

            machines.append(machine)

    sites = g5k._get_sites(clusters)
    if len(sites) > 1:
        raise Exception("Multi-site deployment is not supported yet")

    networks = [constants.NETWORK_INTERFACE]
    enoslib_configuration.update({
        "resources": {
            "machines": machines,
            "networks": networks
        }
    })

    return enoslib_configuration


class Vmong5k(Provider):

    def init(self, configuration, force_deploy=False):
        LOGGER.info("VMonG5K provider")
        enoslib_configuration = _build_enoslib_configuration(configuration)
        _configuration = Configuration.from_dictionnary(enoslib_configuration)
        vmong5k = VMonG5K(_configuration)
        roles, networks = vmong5k.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        LOGGER.info("Destroying VMonG5K deployment")
        enoslib_configuration = _build_enoslib_configuration(env['config'])
        configuration = Configuration.from_dictionnary(enoslib_configuration)
        vmong5k = VMonG5K(configuration)
        vmong5k.destroy()

    def default_config(self):
        return DEFAULT_CONFIG

    def __str__(self):
        return 'VMonG5K'
