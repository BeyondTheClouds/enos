from enos.provider.provider import Provider
from enos.utils.constants import NETWORK_INTERFACE
from enos.utils.extra import gen_enoslib_roles
from enoslib.api import expand_groups
from enoslib.infra.enos_openstack.provider import Openstack as Enos_Openstack

import logging


# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    "type": "openstack",

    # True if Enos needs to create a dedicated network to work with
    # False means you already have a network, subnet and router to
    # your ext_net configured
    "configure_network": True,

    # Name of the network to use or to create
    # It will be use as external network for the upper-cloud
    "network": {'name': 'enos-network'},

    # Name of the subnet to use or to create
    "subnet": {'name': 'enos-subnet', 'cidr': '10.87.23.0/24'},

    # DNS server to use when creating the network
    "dns_nameservers": ['8.8.8.8', '8.8.4.4'],

    # Floating ips pool
    "allocation_pool": {'start': '10.87.23.10', 'end': '10.87.23.100'},

    # Whether one machine must act as gateway
    # - False means that you can connect directly to all the machines
    # started by Enos
    # - True means that one machine will be assigned a floating ip and used
    # as gateway to the others
    "gateway": True,

    # MANDATORY OPTIONS
    'key_name': None,
    'image': None,
    'user': None
}
# + SPHINX_DEFAULT_CONFIG


def _build_enoslib_conf(conf):
    enoslib_conf = conf.get("provider", {})
    if enoslib_conf.get("resources") is not None:
        return enoslib_conf

    resources = conf.get("topology", conf.get("resources", {}))
    machines = []
    for desc in gen_enoslib_roles(resources):
        grps = expand_groups(desc["group"])
        for grp in grps:
            machines.append({
                "flavor": desc["flavor"],
                "roles": [grp, desc["role"]],
                "number": desc["number"],
            })

    # Returning the enoslib description
    # Contribution are welcome for supporting more networks.
    enoslib_conf.update({"resources": {
        "machines": machines,
        "networks": [NETWORK_INTERFACE]}})
    return enoslib_conf


class Openstack(Provider):
    def init(self, conf, force_deploy=False):
        logging.info("Openstack provider")
        enoslib_conf = self.build_config(conf)
        openstack = Enos_Openstack(enoslib_conf)
        roles, networks = openstack.init(force_deploy=force_deploy)
        return roles, networks

    def default_config(self):
        return DEFAULT_CONFIG

    def destroy(self, env):
        conf = env['config']
        enoslib_conf = _build_enoslib_conf(conf)
        openstack = Enos_Openstack(enoslib_conf)
        openstack.destroy()

    def build_config(self, conf):
        return _build_enoslib_conf(conf)
