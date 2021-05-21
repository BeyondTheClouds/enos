# -*- coding: utf-8 -*-
import importlib
import logging
import os
from typing import Dict, Union, Any, Callable

from enos.provider.provider import Provider
import enos.utils.constants as C
from enos.utils.errors import (EnosFilePathError,
                               EnosUnknownProvider)
import enoslib.api as elib_api
from netaddr import IPRange

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
    provider_net = lookup_network(networks, [C.NEUTRON_EXTERNAL_INTERFACE])
    if not provider_net:
        logging.error(f"The {C.NEUTRON_EXTERNAL_INTERFACE} network is missing")
        logging.error("EnOS will try to fix that ....")
        fake_interfaces = [C.FAKE_NEUTRON_EXTERNAL_INTERFACE]
        fake_networks = [C.NEUTRON_EXTERNAL_INTERFACE]

    elib_api.generate_inventory(
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
    provider_net = lookup_network(
        networks, [C.API_INTERFACE, C.NETWORK_INTERFACE])
    if provider_net:
        return provider_net

    msg = "You must declare %s" % " or ".join(
        [C.API_INTERFACE, C.NETWORK_INTERFACE])
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


def make_provider(provider_conf: Union[str, Dict[str, Any]]) -> Provider:
    """Instantiates the provider.

    Seeks into the configuration for the `provider` value. The value
    SHOULD be, either a *string*, or a *dictionary with a `type` key*
    that gives the provider name. Then used this value to instantiate
    and return the provider.

    """
    provider_name = ''
    if isinstance(provider_conf, dict):
        provider_name = provider_conf['type']
    elif isinstance(provider_conf, str):
        provider_name = provider_conf

    if provider_name == "vagrant":
        provider_name = "enos_vagrant"

    module_name = f'enos.provider.{provider_name.lower()}'
    class_name = provider_name.capitalize()

    try:
        module = importlib.import_module(module_name)
        klass = getattr(module, class_name)

        logging.info(f"Loaded provider {klass}")

        return klass()
    except ModuleNotFoundError as e:
        raise EnosUnknownProvider(provider_name) from e


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


def seekpath(path):
    """Seek for an enos file `path` and returns its absolute counterpart.

    Seeking rules are:
    - If `path` is absolute then return it
    - Otherwise, look for `path` in the current working directory
    - Otherwise, look for `path` in the resources directory
    - Otherwise, raise an `EnosFilePathError` exception

    """
    abspath = None

    if os.path.isabs(path):
        abspath = path
    elif os.path.exists(os.path.abspath(path)):
        abspath = os.path.abspath(path)
    elif os.path.exists(os.path.join(C.RSCS_DIR, path)):
        abspath = os.path.join(C.RSCS_DIR, path)
    else:
        raise EnosFilePathError(
            path,
            f"There is no path to {path}, neither in current "
            f"directory ({os.getcwd()}) nor in enos sources ({C.RSCS_DIR}).")

    logging.debug("Seeking %s path resolves to %s", path, abspath)

    return abspath


def setdefault_lazy(env, key: str, thunk_value: Callable[[], Any]):
    if key in env:
        return env[key]
    else:
        value = thunk_value()
        env[key] = value
        return value


def check_env(fn):
    """Decorator for an Enos Task.

    This decorator checks if an environment file exists.

    """
    def decorator(*args, **kwargs):
        # If no directory is provided, set the default one
        resultdir = kwargs.get('--env', C.SYMLINK_NAME)
        # Check if the env file exists
        env_path = os.path.join(resultdir, 'env')
        if not os.path.isfile(env_path):
            raise Exception("The file %s does not exist." % env_path)

        # Proceeds with the function execution
        return fn(*args, **kwargs)
    return decorator
