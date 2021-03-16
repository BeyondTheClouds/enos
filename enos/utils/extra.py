# -*- coding: utf-8 -*-
import copy
import logging
import os
from operator import methodcaller
from typing import Any, Callable

import enoslib.api as api
from enoslib.enos_inventory import EnosInventory
from enoslib.types import Roles
from netaddr import IPRange

from .constants import (API_INTERFACE, ENOS_PATH,
                        FAKE_NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE,
                        NEUTRON_EXTERNAL_INTERFACE)
from .errors import EnosFilePathError, EnosProviderMissingConfigurationKeys

# These roles are mandatory for the
# the original inventory to be valid
# Note that they may be empty
# e.g. if cinder isn't installed storage may be a empty group
# in the inventory
KOLLA_MANDATORY_GROUPS = [
    "control",
    "compute",
    "network",
    "storage"
]


def generate_inventory(roles, networks, base_inventory, dest):
    """
    Generate the inventory.
    It will generate a group for each role in roles and
    concatenate them with the base_inventory file.
    The generated inventory is written in dest
    """
    # NOTE(msimonin): if len(networks) is <= 1
    # provision a fake one that will map the external network

    fake_interfaces = []
    fake_networks = []
    provider_net = lookup_network(networks, [NEUTRON_EXTERNAL_INTERFACE])
    if not provider_net:
        logging.error("The %s network is missing" % NEUTRON_EXTERNAL_INTERFACE)
        logging.error("EnOS will try to fix that ....")
        fake_interfaces = [FAKE_NEUTRON_EXTERNAL_INTERFACE]
        fake_networks = [NEUTRON_EXTERNAL_INTERFACE]

    api.generate_inventory(
        roles,
        networks,
        dest,
        check_networks=True,
        fake_interfaces=fake_interfaces,
        fake_networks=fake_networks
    )

    with open(dest, 'a') as f:
        f.write("\n")
        # generate mandatory groups that are empty
        mandatory = [group for group in KOLLA_MANDATORY_GROUPS
                     if group not in roles.keys()]
        for group in mandatory:
            f.write("[%s]\n" % group)

        with open(base_inventory, 'r') as a:
            for line in a:
                f.write(line)

    logging.info("Inventory file written to " + dest)


def lookup_network(networks, roles):
    """Lookup a network by its roles (in order).
    We assume that one role can't be found in two different networks
    """
    for role in roles:
        for network in networks:
            if role in network["roles"]:
                return network
    return None


def get_vip_pool(networks):
    """Get the provider net where vip can be taken.
    In kolla-ansible this is the network with the api_interface role.
    In kolla-ansible api_interface defaults to network_interface.
    """
    provider_net = lookup_network(networks, [API_INTERFACE, NETWORK_INTERFACE])
    if provider_net:
        return provider_net

    msg = "You must declare %s" % " or ".join(
        [API_INTERFACE, NETWORK_INTERFACE])
    raise Exception(msg)


def pop_ip(provider_net):
    """Picks an ip from the provider_net
    It will first take ips in the extra_ips if possible.
    extra_ips is a list of isolated ips whereas ips described
    by the [provider_net.start, provider.end] range is a continuous
    list of ips.
    """
    # Construct the pool of ips
    extra_ips = provider_net.get('extra_ips', [])
    if len(extra_ips) > 0:
        ip = extra_ips.pop()
        provider_net['extra_ips'] = extra_ips
        return ip

    ips = list(IPRange(provider_net['start'],
                       provider_net['end']))

    # Get the next ip
    ip = str(ips.pop())

    # Remove this ip from the env
    provider_net['end'] = str(ips.pop())

    return ip


def make_provider(provider_conf):
    """Instantiates the provider.

    Seeks into the configuration for the `provider` value. The value
    SHOULD be, either a *string*, or a *dictionary with a `type` key*
    that gives the provider name. Then used this value to instantiate
    and return the provider.

    """
    provider_name = provider_conf['type']\
                    if 'type' in provider_conf\
                    else provider_conf

    if provider_name == "vagrant":
        provider_name = "enos_vagrant"

    package_name = '.'.join(['enos.provider', provider_name.lower()])
    class_name = provider_name.capitalize()

    module = __import__(package_name, fromlist=[class_name])
    klass = getattr(module, class_name)

    logging.info("Loaded provider %s", module)

    return klass()


def gen_enoslib_roles(resources_or_topology):
    """Generator for the resources or topology."""
    for k1, v1 in resources_or_topology.items():
        for k2, v2 in v1.items():
            if isinstance(v2, dict):
                for k3, v3 in v2.items():
                    yield {"group": k1, "role": k3, "flavor": k2, "number": v3}
            else:
                # Puts the resources in a default topology group
                yield {"group": "default_group",
                       "role": k2,
                       "flavor": k1,
                       "number": v2}


def load_config(config, default_provider_config):
    """Load and set default values to the configuration

        Groups syntax is expanded here.
    """
    conf = copy.deepcopy(config)
    conf['provider'] = load_provider_config(
        conf['provider'],
        default_provider_config=default_provider_config)
    return conf


def load_provider_config(provider_config, default_provider_config=None):
    """Load a set default values for the provider configuration.

    This methods checks that every `None` keys in the
    `default_provider_config` are overridden by a value in `provider
    config`.

    """
    default_provider_config = default_provider_config or {}
    if not isinstance(provider_config, dict):
        provider_config = {'type': provider_config}

    # Throw error for missing overridden values of required keys
    missing_overridden = [k for k, v in default_provider_config.items()
                          if v is None and
                          k not in provider_config.keys()]
    if missing_overridden:
        raise EnosProviderMissingConfigurationKeys(missing_overridden)

    # Builds the provider configuration by merging default and user
    # config
    new_provider_config = default_provider_config.copy()
    new_provider_config.update(provider_config)

    return new_provider_config


def seekpath(path):
    """Seek for an enos file `path` and returns its absolute counterpart.

    Seeking rules are:
    - If `path` is absolute then return it
    - Otherwise, look for `path` in the current working directory
    - Otherwise, look for `path` in the source directory
    - Otherwise, raise an `EnosFilePathError` exception

    """
    abspath = None

    if os.path.isabs(path):
        abspath = path
    elif os.path.exists(os.path.abspath(path)):
        abspath = os.path.abspath(path)
    elif os.path.exists(os.path.join(ENOS_PATH, path)):
        abspath = os.path.join(ENOS_PATH, path)
    else:
        raise EnosFilePathError(
            path,
            "There is no path to %s, neither in current "
            "directory (%s) nor enos sources (%s)."
            % (path, os.getcwd(), ENOS_PATH))

    logging.debug("Seeking %s path resolves to %s", path, abspath)

    return abspath


def build_rsc_with_inventory(rsc: Roles, inventory_path: str) -> Roles:
    '''Return a new `rsc` with roles from the inventory.

    In enos, we have a strong binding between enoslib roles and kolla-ansible
    groups.  We need for instance to know hosts of the 'enos/registry' group.
    This method takes an enoslib Roles object and an inventory_path and returns
    a new Roles object that contains all groups (as in the inventory file) with
    their hosts (as in enoslib).

    '''
    inv = EnosInventory(sources=inventory_path)
    rsc_by_name = {h.alias: h for h in api.get_hosts(rsc, 'all')}

    # Build a new rsc with all groups in it
    new_rsc = rsc.copy()
    for grp in inv.list_groups():
        hostnames_in_grp = map(methodcaller('get_name'), inv.get_hosts(grp))
        rsc_in_grp = [rsc_by_name[h_name] for h_name in hostnames_in_grp
                      if h_name in rsc_by_name]
        new_rsc.update({grp: rsc_in_grp})

    return new_rsc


def setdefault_lazy(env, key: str, thunk_value: Callable[[], Any]):
    if key in env:
        return env[key]
    else:
        value = thunk_value()
        env[key] = value
        return value
