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

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'job_name': 'enos-vmong5k',
    'walltime': '02:00:00'
}

DEFAULT_FLAVOUR_BY_ROLE = {
    'control': 'extra-large',
    'network': 'large',
    'compute': 'medium'
}
# + SPHINX_DEFAULT_CONFIG


def _build_enoslib_configuration(configuration):
    _configuration = copy.deepcopy(configuration)
    enoslib_configuration = _configuration.get("provider", {})
    enoslib_configuration.pop("type", None)
    if "resources" in enoslib_configuration:
        return enoslib_configuration

    machines = []
    clusters = set()
    resources = _configuration.get("resources", {})
    resources = _configuration.get("topology", resources)
    for description in extra.gen_enoslib_roles(resources):
        for group in api.expand_groups(description["group"]):
            clusters.add(description["flavor"])
            role = description["role"]
            machine = {
                "roles": [group, role],
                "number": description["number"],
                "cluster": description["flavor"],
                # set default to 'medium' from enoslib FLAVOURS
                "flavour": DEFAULT_FLAVOUR_BY_ROLE.get(role, 'medium')
            }

            machines.append(machine)

    sites = g5k._get_sites(clusters)
    if len(sites) > 1:
        raise Exception("Multi-site deployment is not supported yet")

    enoslib_configuration.update({
        "resources": {
            "machines": machines,
            "networks": [constants.NETWORK_INTERFACE]
        }
    })

    return enoslib_configuration


def _get_provider_instance(configuration):
    enoslib_configuration = _build_enoslib_configuration(configuration)
    _configuration = Configuration.from_dictionnary(enoslib_configuration)
    return VMonG5K(_configuration)


class Vmong5k(Provider):

    def init(self, configuration, force_deploy=False):
        LOGGER.info("Initializing VMonG5K provider")
        vmong5k = _get_provider_instance(configuration)
        return vmong5k.init(force_deploy)  # roles, networks

    def destroy(self, env):
        LOGGER.info("Destroying VMonG5K deployment")
        vmong5k = _get_provider_instance(env['config'])
        vmong5k.destroy()

    def default_config(self):
        return DEFAULT_CONFIG

    def __str__(self):
        return 'Vmong5k'
