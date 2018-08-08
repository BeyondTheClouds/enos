import logging
from enos.provider.provider import Provider
from enos.utils.extra import gen_enoslib_roles
import enoslib.infra.enos_vagrant.provider as enoslib_vagrant
from enoslib.api import expand_groups

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'backend': 'virtualbox',
    'box': 'generic/debian9',
    'user': 'root',
}
# + SPHINX_DEFAULT_CONFIG


def _build_enoslib_conf(conf):
    # This is common to every provider
    enoslib_conf = conf.get("provider", {})
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
                "flavor": desc["flavor"],
                "roles": [grp, desc["role"]],
                "number": desc["number"],
                "networks": ["network_interface", "neutron_external_interface"]
            })

    enoslib_conf.update({"resources": {"machines": machines}})
    return enoslib_conf


class Enos_vagrant(Provider):

    def init(self, conf, force_deploy=False):
        logging.info("Vagrant provider")
        enoslib_conf = _build_enoslib_conf(conf)
        vagrant = enoslib_vagrant.Enos_vagrant(enoslib_conf)
        roles, networks = vagrant.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        logging.info("Destroying vagrant deployment")
        enoslib_conf = _build_enoslib_conf(env['config'])
        vagrant = enoslib_vagrant.Enos_vagrant(enoslib_conf)
        vagrant.destroy()

    def default_config(self):
        return DEFAULT_CONFIG
