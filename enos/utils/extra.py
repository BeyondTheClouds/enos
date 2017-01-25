# -*- coding: utf-8 -*-
from constants import TEMPLATE_DIR

from ansible.inventory import Inventory
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.executor.playbook_executor import PlaybookExecutor
from itertools import groupby

from netaddr import IPRange

from subprocess import call
import jinja2
import os
import yaml
import logging
import re

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


def run_ansible(playbooks, inventory_path, extra_vars={}, tags=None):
    variable_manager = VariableManager()
    loader = DataLoader()

    inventory = Inventory(loader=loader,
        variable_manager=variable_manager,
        host_list=inventory_path)

    variable_manager.set_inventory(inventory)

    if extra_vars:
        variable_manager.extra_vars = extra_vars

    passwords = {}

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
                                     'check', 'tags'])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection='ssh',
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=False,
                      become_method=None, become_user=None,
                      remote_user=None, verbosity=None, check=False,
                      tags=tags)

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
        if len(unreachable_hosts) > 0:
            logging.error("Unreachable hosts: %s" % unreachable_hosts)


def render_template(template_name, vars, output_path):
    loader = jinja2.FileSystemLoader(searchpath=TEMPLATE_DIR)
    env = jinja2.Environment(loader=loader)
    template = env.get_template(template_name)

    rendered_text = template.render(vars)
    with open(output_path, 'w') as f:
        f.write(rendered_text)


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

    def generate_inventory_string(n, role):
        i = [n.address, "ansible_ssh_user=root"]
        if n.port is not None:
            i.append("ansible_port=%s" % n.port)
        if n.keyfile is not None:
            i.append("ansible_ssh_private_key_file=%s" % n.keyfile)
        # extra
        i.append("ansible_ssh_common_args=\"-o StrictHostKeyChecking=no\"")
        i.append("g5k_role=%s" % role)
        return " ".join(i)

    inventory = []
    mandatory = [group for group in KOLLA_MANDATORY_GROUPS
                       if group not in roles.keys()]
    for group in mandatory:
        inventory.append("[%s]" % (group))

    for role, nodes in roles.items():
        inventory.append("[%s]" % (role))
        inventory.extend(map(lambda n: generate_inventory_string(n, role), nodes))
    inventory.append("\n")
    return "\n".join(inventory)


def generate_kolla_files(config_vars, kolla_vars, directory):
    # get the static parameters from the config file
    kolla_globals = config_vars
    # add the generated parameters
    kolla_globals.update(kolla_vars)
    # write to file in the result dir
    globals_path = os.path.join(directory, 'globals.yml')
    with open(globals_path, 'w') as f:
        yaml.dump(kolla_globals, f, default_flow_style=False)

    logging.info("Wrote " + globals_path)

    # copy the passwords file
    passwords_path = os.path.join(directory, "passwords.yml")
    call("cp %s/passwords.yml %s" % (TEMPLATE_DIR, passwords_path), shell=True)
    logging.info("Password file is copied to  %s" % (passwords_path))

    # admin openrc
    admin_openrc_path = os.path.join(directory, 'admin-openrc')
    admin_openrc_vars = {
        'keystone_address': kolla_vars['kolla_internal_vip_address']
    }
    render_template('admin-openrc.jinja2',
                    admin_openrc_vars,
                    admin_openrc_path)
    logging.info("admin-openrc generated in %s" % (admin_openrc_path))

def to_abs_path(path):
    """
    if set, path is considered relative to the current working directory
    if not just fail
    Note: this does not check the existence
    """
    if os.path.isabs(path):
        return path
    else:
       return os.path.join(os.getcwd(), path) 

def build_resources(topology):
    """
    Build the resource list
    For now we are just aggregating all the resources
    This could be part of a flat resource builder
    """

    def merge_add(cluster_roles, roles):
        """ merge two dicts, sum the values"""
        for role, nb in roles.items():
            cluster_roles.setdefault(role, 0)
            cluster_roles[role] = cluster_roles[role] + nb

    resource = {}
    for group, clusters in topology.items():
        for cluster, roles in clusters.items():
            resource.setdefault(cluster, {})
            merge_add(resource[cluster], roles)
    return resource

def expand_groups(grp):
    """
    Expand group names.
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
    "Picks an ip from env['provider_net']."
    # Construct the pool of ips
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
        (vagrant)...

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

    resources = config['resources']
    if 'topology' in config:
        resources = config['topology']

    rindexes = _build_indexes(resources)
    # indexes = [['resources', 'paravance', 'controller', 2],
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
        key=lambda indexes: len(indexes) if indexes[-2] != "compute" else -1,
        reverse=True)
    for indexes in rindexes:
        if indexes[nb_idx] <= 0:
            continue
        cluster = indexes[cluster_idx]
        role = indexes[role_idx]
        nb = indexes[nb_idx]
        nodes = pick_nodes(pools[cluster], nb)
        # putting those nodes in all super groups
        for role in indexes[0:nb_idx]:
            roles.setdefault(role, []).extend(nodes)
        indexes[nb_idx] = indexes[nb_idx] - nb

    at_least_one = all(len(n) >= 1 for n in roles.values())
    if not at_least_one:
        # NOTE(msimonin): Maybe make a warning only
        raise Exception("Role doesn't have at least one node each")

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

    returns [a,1,z,1],[a,1,t,2],[a,2,u,3]...
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
