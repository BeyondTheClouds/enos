# -*- coding: utf-8 -*-
import enoslib.api as api
from .errors import (EnosFailedHostsError, EnosUnreachableHostsError,
                     EnosProviderMissingConfigurationKeys,
                     EnosFilePathError)
from collections import namedtuple
from .constants import (ENOS_PATH, ANSIBLE_DIR, VENV_KOLLA,
                        NEUTRON_EXTERNAL_INTERFACE, FAKE_NEUTRON_EXTERNAL_INTERFACE,
                        NETWORK_INTERFACE, API_INTERFACE)
from itertools import groupby
from netaddr import IPRange

import logging
import operator
import os
import re
from subprocess import check_call
import time
import yaml

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



def get_kolla_required_values(env):
    """Returns a dictionary with all values required by kolla-ansible
based on the Enos environment.

    """
    values = {
        'kolla_internal_vip_address': env['config']['vip'],
        'influx_vip':                 env['config']['influx_vip'],
        'kolla_ref':                  env['config']['kolla_ref'],
        'resultdir':                  env['resultdir']
    }

    # Manage monitoring stack
    if 'enable_monitoring' in env['config']:
        values['enable_monitoring'] = env['config']['enable_monitoring']

    # Manage docker registry
    registry_type = env['config']['registry']['type']
    if registry_type == 'internal':
        values['docker_registry'] = \
            "%s:4000" % env['config']['registry_vip']
    elif registry_type == 'external':
        values['docker_registry'] = \
            "%s:%s" % (env['config']['registry']['ip'],
                       env['config']['registry']['port'])

    return values


def mk_kolla_values(src_path, required_values, user_values):
    """Builds a dictionary with all kolla values.

    :param src_path: Path to kolla-ansible sources.

    :param required_values: Values required by kolla-ansible.

    :param user_values: User specic kolla values as defined into
        the reservation file.

    return values related to kolla-ansible
    """
    kolla_values = {}

    # Get kolla-ansible `all.yml` values
    with open(os.path.join(
            src_path, 'ansible', 'group_vars', 'all.yml'), 'r') as f:
        kolla_values.update(yaml.load(f))

    # Override with required values
    kolla_values.update(required_values)

    # Override with user specific values
    kolla_values.update(user_values)

    return kolla_values


def mk_enos_values(env):
    "Builds a dictionary with all enos values based on the environment."
    enos_values = {}

    # Get all kolla values
    enos_values.update(mk_kolla_values(
        os.path.join(env['resultdir'], 'kolla'),
        get_kolla_required_values(env),
        env['config']['kolla']))

    # Update with user specific values (except already got kolla)
    enos_values.update(
        {k: v for k, v in env['config'].items() if k != "kolla"})

    # Add the Current Working Directory (cwd)
    enos_values.update(cwd=env['cwd'])

    return enos_values


# TODO(rcherrueau): Remove this helper function and move code into
# enos.install_os when the following FIXME will be addressed.
def bootstrap_kolla(env):
    """Setups all necessities for calling kolla-ansible.

    - Patches kolla-ansible sources (if any).
    - Builds globals.yml into result dir.
    - Builds password.yml into result dir.
    - Builds admin-openrc into result dir.
    """
    # Write the globals.yml file in the result dir.
    #
    # FIXME: Find a neat way to put this into the next bootsrap_kolla
    # playbook. Then, remove this util function and call directly the
    # playbook from `enos os`.
    globals_path = os.path.join(env['resultdir'], 'globals.yml')
    globals_values = get_kolla_required_values(env)
    globals_values.update(env['config']['kolla'])
    globals_values.update(cwd=env['cwd'])
    with open(globals_path, 'w') as f:
        yaml.dump(globals_values, f, default_flow_style=False)

    # Patch kolla-ansible sources + Write admin-openrc and
    # password.yml in the result dir
    enos_values = mk_enos_values(env)
    playbook = os.path.join(ANSIBLE_DIR, 'bootstrap_kolla.yml')

    api.run_ansible([playbook], env['inventory'], extra_vars=enos_values)


def expand_groups(grp):
    """Expand group names.
    e.g:
        * grp[1-3] -> [grp1, grp2, grp3]
        * grp1 -> [grp1]
    """
    p = re.compile('(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\]')
    m = p.match(grp)
    if m is not None:
        s = int(m.group('start'))
        e = int(m.group('end'))
        n = m.group('name')
        return map(lambda x: n + str(x), range(s, e + 1))
    else:
        return [grp]


def expand_topology(topology):
    expanded = {}
    for grp, desc in topology.items():
        grps = expand_groups(grp)
        for g in grps:
            expanded[g] = desc
    return expanded

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

    msg = "You must declare %s" % " or ".join([API_INTERFACE, NETWORK_INTERFACE])
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


def make_provider(env):
    """Instantiates the provider.

    Seeks into the configuration for the `provider` value. The value
    SHOULD be, either a *string*, or a *dictionary with a `type` key*
    that gives the provider name. Then used this value to instantiate
    and return the provider.

    """
    
    provider_name = env['config']['provider']['type']\
                    if 'type' in env['config']['provider']\
                    else env['config']['provider']

    if provider_name == "vagrant":
        provider_name = "enos_vagrant"

    package_name = '.'.join(['enos.provider', provider_name.lower()])
    class_name = provider_name.capitalize()

    module = __import__(package_name, fromlist=[class_name])
    klass = getattr(module, class_name)

    logging.info("Loaded provider %s", module)

    return klass()


def get_total_wanted_machines(resources):
    """Get the total number of machines
    wanted given ther resource description."""
    return sum(reduce(operator.add,
                      map(lambda r: r.values(), resources.values()),
                      []))


def gen_enoslib_roles(resources_or_topology):
    """Generator for the resources or topology."""
    for k1, v1 in resources_or_topology.items():
        for k2, v2 in v1.items():
            if isinstance(v2, dict):
                for k3, v3 in v2.items():
                    yield {"group": k1, "role": k3, "flavor": k2, "number": v3}
            else:
                # Puts the resources in a default topology group
                yield {"group": "default_group", "role": k2, "flavor": k1, "number": v2}


def gen_resources(resources):
    """Generator for the resources in the config file."""
    for l1, roles in resources.items():
        for l2, l3 in roles.items():
            yield l1, l2, l3


def load_config(config, provider_topo2rsc, default_provider_config):
    """Load and set default values to the configuration

        Groups syntax is expanded here.
    """
    conf = config.copy()
    if 'topology' in config:
        # expand the groups first
        conf['topology'] = expand_topology(config['topology'])
        # We are here using a flat combination of the resource
        # resulting in (probably) deploying one single region
        conf['resources'] = provider_topo2rsc(conf['topology'])

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

def check_call_in_venv(venv_dir, cmd):
    """Calls command in kolla virtualenv."""
    def check_venv(venv_path):

        if not os.path.exists(venv_path):
            check_call("virtualenv %s" % venv_path, shell=True)
            check_call_in_venv(venv_dir, "pip install --upgrade pip")

    cmd_in_venv = []
    cmd_in_venv.append(". %s/bin/activate " % venv_dir)
    cmd_in_venv.append('&&')
    if isinstance(cmd, list):
        cmd_in_venv.extend(cmd)
    else:
        cmd_in_venv.append(cmd)
    check_venv(venv_dir)
    _cmd = ' '.join(cmd_in_venv)
    logging.debug(_cmd)
    return check_call(_cmd, shell=True)


def in_kolla(cmd):
     check_call_in_venv(VENV_KOLLA, cmd)
