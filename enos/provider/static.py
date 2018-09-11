# -*- coding: utf-8 -*-
import copy
import logging

from enoslib.api import expand_groups
import enoslib.infra.enos_static.provider as enos_static

from enos.provider.provider import Provider

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
}
# + SPHINX_DEFAULT_CONFIG

LOGGER = logging.getLogger(__name__)


def _gen_enoslib_roles(resources_or_topology):
    """
    Generator for the resources or topology.

    NOTE(msimonin): static provider resources description is slightly different
    from the other providers
    """
    def _gen_machines(machine_or_list, default):
        machine = default
        if isinstance(machine_or_list, list):
            for m in machine_or_list:
                machine.update(m)
                yield machine
        else:
            machine.update(machine_or_list)
            yield machine

    for k1, v1 in resources_or_topology.items():
        if isinstance(v1, dict):
            for k2, v2 in v1.items():
                machine = {"group": k1, "role": k2}
                for m in _gen_machines(v2, machine):
                    yield m
        else:
            machine = {"group": "default_group", "role": k1}
            for m in _gen_machines(v1, machine):
                yield m


def _build_enoslib_conf(config):
    conf = copy.deepcopy(config)
    enoslib_conf = conf.get("provider")
    if enoslib_conf.get("resources") is not None:
        return enoslib_conf

    # We fall here in the legacy mode but a bit modified
    # for the networks description
    networks = enoslib_conf["networks"]

    resources = conf.get("topology", conf.get("resources", {}))
    machines = []
    for desc in _gen_enoslib_roles(resources):

        grps = expand_groups(desc["group"])
        role = desc["role"]
        for grp in grps:
            machine = {
                "roles": [grp, role]
            }
            machine.update(desc)
            machines.append(machine)

    enoslib_conf = {
        "resources": {
            "machines": machines,
            "networks": networks
        }
    }

    return enoslib_conf


class Static(Provider):
    def init(self, conf, force_deploy=False):
        LOGGER.info("Static provider")
        enoslib_conf = _build_enoslib_conf(conf)
        static = enos_static.Static(enoslib_conf)
        roles, networks = static.init(force_deploy)
        return roles, networks

    def destroy(self, env):
        # NOTE(msimonin): We can't destroy static resources
        # This would be mean
        pass

    def default_config(self):
        return DEFAULT_CONFIG
