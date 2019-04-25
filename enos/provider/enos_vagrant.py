import copy
import logging
from enos.provider.provider import Provider
from enos.utils.extra import gen_enoslib_roles
import enoslib.infra.enos_vagrant.provider as enoslib_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration
from enoslib.api import expand_groups

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'backend': 'virtualbox',
    'box': 'generic/debian9',
    'user': 'root',
}
# + SPHINX_DEFAULT_CONFIG

LOGGER = logging.getLogger(__name__)


def _build_enoslib_conf(config):
    conf = copy.deepcopy(config)
    enoslib_conf = conf.get("provider", {})
    enoslib_conf.pop("type", None)
    if enoslib_conf.get("resources") is not None:
        return enoslib_conf

    # This coould be common to everyone
    # Enoslib needs to be patched here
    resources = conf.get("topology", conf.get("resources", {}))
    machines = []
    for desc in gen_enoslib_roles(resources):
        # NOTE(msimonin): in the basic definition, we consider only
        # two networks
        grps = expand_groups(desc["group"])
        for grp in grps:
            machines.append({
                "flavour": desc["flavor"],
                "roles": [grp, desc["role"]],
                "number": desc["number"],
            })

    networks = [
        {"roles": ["network_interface"], "cidr": "192.168.42.0/24"},
        {"roles": ["neutron_external_interface"], "cidr": "192.168.43.0/24"}
    ]
    enoslib_conf.update({"resources": {"machines": machines,
                                       "networks": networks}})
    return enoslib_conf


class Enos_vagrant(Provider):

    def init(self, conf, force_deploy=False):
        LOGGER.info("Vagrant provider")
        enoslib_conf = _build_enoslib_conf(conf)
        _conf = Configuration.from_dictionnary(enoslib_conf)
        vagrant = enoslib_vagrant.Enos_vagrant(_conf)
        roles, networks = vagrant.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        LOGGER.info("Destroying vagrant deployment")
        enoslib_conf = _build_enoslib_conf(env['config'])
        vagrant = enoslib_vagrant.Enos_vagrant(enoslib_conf)
        vagrant.destroy()

    def default_config(self):
        return DEFAULT_CONFIG

    def __str__(self):
        return 'Vagrant'
