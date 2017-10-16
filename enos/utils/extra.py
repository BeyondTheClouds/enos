# -*- coding: utf-8 -*-
from .errors import (EnosFailedHostsError, EnosUnreachableHostsError,
                     EnosProviderMissingConfigurationKeys,
                     EnosFilePathError)
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from collections import namedtuple
from constants import (ENOS_PATH, ANSIBLE_DIR, NETWORK_IFACE,
                       EXTERNAL_IFACE)
from itertools import groupby
from netaddr import IPRange

import logging
import operator
import os
import re
import time
import yaml

# These roles are mandatory for the
# the original inventory to be valid
# Note that they may be empy
# e.g. if cinder isn't installed storage may be a empty group
# in the inventory
KOLLA_MANDATORY_GROUPS = [
    "control",
    "compute",
    "network",
    "storage"
]


def run_ansible(playbooks, inventory_path, extra_vars={},
        tags=None, on_error_continue=False):
    extra_vars = extra_vars or {}
    variable_manager = VariableManager()
    loader = DataLoader()

    inventory = Inventory(loader=loader,
        variable_manager=variable_manager,
        host_list=inventory_path)

    variable_manager.set_inventory(inventory)

    if extra_vars:
        variable_manager.extra_vars = extra_vars

    if tags is None:
        tags = []

    passwords = {}
    # NOTE(msimonin): The ansible api is "low level" in the
    # sense that we are redefining here all the default values
    # that are usually enforce by ansible called from the cli
    Options = namedtuple('Options', ['listtags', 'listtasks',
                                     'listhosts', 'syntax',
                                     'connection', 'module_path',
                                     'forks', 'private_key_file',
                                     'ssh_common_args',
                                     'ssh_extra_args',
                                     'sftp_extra_args',
                                     'scp_extra_args', 'become',
                                     'become_method', 'become_user',
                                     'remote_user', 'verbosity',
                                     'check', 'tags', 'pipelining'])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection='ssh',
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=None,
                      become_method='sudo', become_user='root',
                      remote_user=None, verbosity=2, check=False,
                      tags=tags, pipelining=True)

    for path in playbooks:
        logging.info("Running playbook %s with vars:\n%s" % (path, extra_vars))

        pbex = PlaybookExecutor(
            playbooks=[path],
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=options,
            passwords=passwords
        )

        code = pbex.run()
        stats = pbex._tqm._stats
        hosts = stats.processed.keys()
        result = [{h: stats.summarize(h)} for h in hosts]
        results = {'code': code, 'result': result, 'playbook': path}
        print(results)

        failed_hosts = []
        unreachable_hosts = []

        for h in hosts:
            t = stats.summarize(h)
            if t['failures'] > 0:
                failed_hosts.append(h)

            if t['unreachable'] > 0:
                unreachable_hosts.append(h)

        if len(failed_hosts) > 0:
            logging.error("Failed hosts: %s" % failed_hosts)
            if not on_error_continue:
                raise EnosFailedHostsError(failed_hosts)
        if len(unreachable_hosts) > 0:
            logging.error("Unreachable hosts: %s" % unreachable_hosts)
            if not on_error_continue:
                raise EnosUnreachableHostsError(unreachable_hosts)


def wait_ssh(env, retries=100, interval=30):
    """Wait for the resources to be ssh-reachable

    Let ansible initiates a communication and retries if needed.

    :param retries: Number of time we'll be retrying an SSH connection
    :param interval: Interval to wait in seconds between two retries

    """
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'action': 'ping', 'tc_output_dir': env['resultdir']}

    for i in range(0, retries):
        try:
            run_ansible([utils_playbook],
                        env['inventory'],
                        extra_vars=options,
                        on_error_continue=False)
            break
        except EnosUnreachableHostsError as e:
            logging.info("Hosts unreachable: %s " % e.hosts)
            logging.info("Retrying... %s/%s" % (i + 1, retries))
            time.sleep(interval)
    else:
        raise Exception('Maximum retries reached')


def generate_inventory(roles, base_inventory, dest):
    """
    Generate the inventory.
    It will generate a group for each role in roles and
    concatenate them with the base_inventory file.
    The generated inventory is written in dest
    """
    with open(dest, 'w') as f:
        f.write(to_ansible_group_string(roles))
        with open(base_inventory, 'r') as a:
            for line in a:
                f.write(line)

    logging.info("Inventory file written to " + dest)


def generate_inventory_string(n, role):
    i = [n.alias, "ansible_host=%s" % n.address]
    if n.user is not None:
        i.append("ansible_ssh_user=%s" % n.user)
    if n.port is not None:
        i.append("ansible_port=%s" % n.port)
    if n.keyfile is not None:
        i.append("ansible_ssh_private_key_file=%s" % n.keyfile)
    # Disabling hostkey ckecking
    common_args = []
    common_args.append("-o StrictHostKeyChecking=no")
    common_args.append("-o UserKnownHostsFile=/dev/null")
    forward_agent = n.extra.get('forward_agent', False)
    if forward_agent:
        common_args.append("-o ForwardAgent=yes")

    gateway = n.extra.get('gateway', None)
    if gateway is not None:
        proxy_cmd = ["ssh -W %h:%p"]
        # Disabling also hostkey checking for the gateway
        proxy_cmd.append("-o StrictHostKeyChecking=no")
        proxy_cmd.append("-o UserKnownHostsFile=/dev/null")
        gateway_user = n.extra.get('gateway_user', n.user)
        if gateway_user is not None:
            proxy_cmd.append("-l %s" % gateway_user)

        proxy_cmd.append(gateway)
        proxy_cmd = " ".join(proxy_cmd)
        common_args.append("-o ProxyCommand=\"%s\"" % proxy_cmd)

    common_args = " ".join(common_args)
    i.append("ansible_ssh_common_args='%s'" % common_args)
    i.append("g5k_role=%s" % role)

    # Add custom variables
    for k, v in n.extra.items():
        if k not in ["gateway", "gateway_user", "forward_agent"]:
            i.append("%s=%s" % (k, v))
    return " ".join(i)


def to_ansible_group_string(roles):
    """Transform a role list (oar) to an ansible list of groups (inventory)
    Make sure the mandatory group are set as well
    e.g
    {
    'role1': ['n1', 'n2', 'n3'],
    'role12: ['n4']

    }
    ->
    [role1]
    n1
    n2
    n3
    [role2]
    n4
    """
    inventory = []
    mandatory = [group for group in KOLLA_MANDATORY_GROUPS
                       if group not in roles.keys()]
    for group in mandatory:
        inventory.append("[%s]" % (group))

    for role, nodes in roles.items():
        inventory.append("[%s]" % (role))
        inventory.extend(map(lambda n: generate_inventory_string(n, role),
                             nodes))
    inventory.append("\n")
    return "\n".join(inventory)


def get_kolla_required_values(env):
    """Returns a dictionary with all values required by kolla-ansible
based on the Enos environment.

    """
    values = {
        'network_interface':          env['eths'][NETWORK_IFACE],
        'kolla_internal_vip_address': env['config']['vip'],
        'neutron_external_interface': env['eths'][EXTERNAL_IFACE],
        'neutron_external_address':   env['config']['external_vip'],
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
    run_ansible([playbook], env['inventory'], extra_vars=enos_values)


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


def pop_ip(env=None):
    """Picks an ip from env['provider_net'].

    It will first take ips in the extra_ips if possible.
    extra_ips is a list of isolated ips whereas ips described
    by the [provider_net.start, provider.end] range is a continuous
    list of ips.
    """
    # Construct the pool of ips
    extra_ips = env['provider_net'].get('extra_ips', [])
    if len(extra_ips) > 0:
        ip = extra_ips.pop()
        env['provider_net']['extra_ips'] = extra_ips
        return ip

    ips = list(IPRange(env['provider_net']['start'],
                       env['provider_net']['end']))

    # Get the next ip
    ip = str(ips.pop())

    # Remove this ip from the env
    env['provider_net']['end'] = str(ips.pop())

    return ip


def build_roles(config, deployed_nodes, keyfnc):
    """Returns a dict that maps each role to a list of G5k nodes::

    :param config: the configuration (usually read from the yaml configuration
        file)

    :param deployed_nodes: the deployed nodes to distribute accros roles.
        Must contains all the information needed for keyfnc to group nodes.

    :param keyfnc: lambda used to group nodes by cluster (g5k), size
        (vagrant)... take an element of deployed_nodes and returns a value to
        group on

    example:
    config:
       resources:
            paravance:
                controller: 2
            econome:
                compute: 1

    deployed_nodes = ['paravance-1', 'paravance-5', 'econome-1']

    returns
        { 'controller': ['paravance-1', 'paravance-5'],
          'compute': ['econome-1'] }
    """
    def mk_pools():
        "Indexes a node by the keyfnc to construct pools of nodes."
        pools = {}
        for cluster, nodes in groupby(deployed_nodes, keyfnc):
            pools.setdefault(cluster, []).extend(list(nodes))
        return pools

    def pick_nodes(pool, n):
        "Picks a maximum of n nodes in a pool of nodes."
        nodes = pool[:n]
        del pool[:n]
        return nodes

    cluster_idx = -3
    role_idx = -2
    nb_idx = -1

    resources = config.setdefault('topology', config['resources'])
    rindexes = _build_indexes(resources)
    # rindexes = [['resources', 'paravance', 'controller', 2],
    #            ['resource', 'econome', 'compute', 1]]
    # Thus we need to pick 2 nodes belonging to paravance cluster
    # and assign them to the controller role.
    # then 1 node belonging to econome

    pools = mk_pools()
    roles = {}
    # distribute the nodes "compute" role is assumed to be the less important
    # to fill
    # NOTE(msimonin): The above assumption is questionnable but
    # corresponds to the case where compute nodes number >> other services
    # number and some missing compute nodes isn't catastrophic
    rindexes = sorted(rindexes,
        key=lambda indexes: len(indexes)
                      if indexes[role_idx] != "compute" else -1,
        reverse=True)
    for indexes in rindexes:
        cluster = indexes[cluster_idx]
        role = indexes[role_idx]
        nb = indexes[nb_idx]
        nodes = pick_nodes(pools[cluster], nb)
        # putting those nodes in all super groups
        for role in indexes[0:nb_idx]:
            roles.setdefault(role, []).extend(nodes)
        indexes[nb_idx] = indexes[nb_idx] - nb

    logging.info(roles)
    return roles


def _build_indexes(resources):
    """Recursively build all the paths in a dict where final values
    are int.

    :param resources: the dict of resources to explore

    example:

    a:
        1:
            z:1
            t:2
        2:
            u:3
            v:4
    b:
        4:
            x:5
            y:6
        5:
            w:7

    returns [[a,1,z,1],[a,1,t,2],[a,2,u,3]...]
    """
    # concatenate the current keys with the already built indexes
    if type(resources) == int:
        return [[resources]]
    all_indexes = []
    # NOTE(msimonin): we sort to ensure the order will remain the same
    # on subsequent calls
    for key, value in sorted(resources.items(), key=lambda x: x[0]):
        rindexes = _build_indexes(value)
        for indexes in rindexes:
            s = [key]
            s.extend(list(indexes))
            all_indexes.append(s)
    return all_indexes


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
