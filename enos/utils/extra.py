# -*- coding: utf-8 -*-
from constants import TEMPLATE_DIR

from ansible.inventory import Inventory
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.executor.playbook_executor import PlaybookExecutor

from subprocess import call
import jinja2
import os
import yaml
import logging

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
    """
    Transform a role list (oar) to an ansible list of groups (inventory)
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
        inventory.extend(map(
            lambda n: "%s ansible_ssh_user=root g5k_role=%s"
            % (n.address, role),
            nodes))
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
