#! /usr/bin/env python

import sys, os, subprocess

from ansible.inventory import Inventory
import ansible.callbacks
import ansible.playbook

import jinja2
from execo.log import style
from execo_engine import logger
from engine.g5k_engine import G5kEngine

import yaml

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
SYMLINK_NAME = os.path.join(SCRIPT_PATH, 'current')
TEMPLATE_DIR = os.path.join(SCRIPT_PATH, 'templates')

KOLLA_REPO = 'https://git.openstack.org/openstack/kolla'
KOLLA_BRANCH = 'stable/mitaka'
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



class KollaG5k(G5kEngine):
    def __init__(self):
        super(KollaG5k, self).__init__()

    def run(self):
        self.load()

        self.get_job()

        deployed, undeployed = self.deploy()
        if len(undeployed) > 0:
            sys.exit(31)

        roles = self.build_roles()

        # Get an IP for 
        # kolla (haproxy)
        # docker registry 
        # influx db 
        vip_addresses = self.get_free_ip(3)
        print(vip_addresses)
        # Get the NIC devices of the reserved cluster
        # XXX: this only works if all nodes are on the same cluster,
        # or if nodes from different clusters have the same devices
        interfaces = self.get_cluster_nics(self.config['resources'].keys()[0])

        # TODO workarround
        self.exec_command_on_nodes(self.deployed_nodes, 'apt-get update && apt-get -y --force-yes install apt-transport-https',
            'Workarround: installing apt-transport-https...')

        # Install python on the nodes
        self.exec_command_on_nodes(self.deployed_nodes, 'apt-get -y install python',
            'Installing Python on all the nodes...')

        # Run the Ansible playbooks
        playbooks = ['ansible/site.yml']

        inventory_path = os.path.join(self.result_dir, 'multinode')
        base_inventory = self.config['inventory']
        generate_inventory(roles, base_inventory, inventory_path)

        extra_vars = {
            'registry_vip': str(vip_addresses[1]),
            'influx_vip': str(vip_addresses[2]),
            'network_interface': str(interfaces[0])
        }

        extra_vars.update(self.config)
        run_ansible(playbooks, inventory_path, extra_vars)

        # Clone or pull Kolla
        if os.path.isdir('kolla'):
            logger.info("Pulling Kolla...")
            os.system("cd kolla; git pull > /dev/null")
        else:
            logger.info("Cloning Kolla...")
            os.system("git clone %s -b %s > /dev/null" % (KOLLA_REPO, KOLLA_BRANCH))

        # Generate the inventory file
        kolla_vars = {
            'kolla_internal_vip_address' : str(vip_addresses[0]),
            'network_interface'          : str(interfaces[0]),
            'neutron_external_interface' : str(interfaces[1])
        }

        # Generating Ansible globals.yml
        generate_kolla_files(self.config["kolla"], kolla_vars, self.result_dir)

        link = os.path.abspath(SYMLINK_NAME)
        try:
            os.remove(link)
        except OSError:
            pass
        os.symlink(self.result_dir, link)

        ## create ssh tunnels file
        self.generate_sshtunnels(str(vip_addresses[0]))

        logger.info("Symlinked %s to %s" % (self.result_dir, link))
        logger.info("You can now run ./02_deploy_kolla.sh")

        sys.exit(0)

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

    logger.info("Inventory file written to " + style.emph(dest))

def generate_kolla_files(config_vars, kolla_vars, directory):
    # get the static parameters from the config file
    kolla_globals = config_vars
    # add the generated parameters 
    kolla_globals.update(kolla_vars)
    # write to file in the result dir
    globals_path = os.path.join(directory, 'globals.yml')
    with open(globals_path, 'w') as f:
        yaml.dump(kolla_globals, f, default_flow_style=False)

    logger.info("Wrote " + style.emph(globals_path))

    # copy the passwords file
    passwords_path = os.path.join(directory, "passwords.yml")
    os.system("cp %s/passwords.yml %s" % (TEMPLATE_DIR, passwords_path))
    logger.info("Password file is copied to  %s" % (passwords_path))
    
    # admin openrc 
    admin_openrc_path = os.path.join(directory, 'admin-openrc')
    admin_openrc_vars = {
        'keystone_address': kolla_vars['kolla_internal_vip_address']
    }
    render_template('templates/admin-openrc.jinja2', admin_openrc_vars, admin_openrc_path)
    logger.info("admin-openrc generated in %s" % (admin_openrc_path))


def run_ansible(playbooks, inventory_path, extra_vars):
    inventory = Inventory(inventory_path)

    for path in playbooks:
        logger.info("Running playbook %s with vars:\n%s" % (style.emph(path), extra_vars))
        stats = ansible.callbacks.AggregateStats()
        playbook_cb = ansible.callbacks.PlaybookCallbacks(verbose=1)

        pb = ansible.playbook.PlayBook(
            playbook=path,
            inventory=inventory,
            extra_vars=extra_vars,
            stats=stats,
            callbacks=playbook_cb,
            runner_callbacks=ansible.callbacks.PlaybookRunnerCallbacks(stats, verbose=1),
            forks=10
        )

        pb.run()

        hosts = pb.stats.processed.keys()
        failed_hosts = []
        unreachable_hosts = []

        for h in hosts:
            t = pb.stats.summarize(h)
            if t['failures'] > 0:
                failed_hosts.append(h)

            if t['unreachable'] > 0:
                unreachable_hosts.append(h)

        if len(failed_hosts) > 0:
            logger.error("Failed hosts: %s" % failed_hosts)
        if len(unreachable_hosts) > 0:
            logger.error("Unreachable hosts: %s" % unreachable_hosts)

def render_template(template_path, vars, output_path):
    loader = jinja2.FileSystemLoader(searchpath='.')
    env = jinja2.Environment(loader=loader)
    template = env.get_template(template_path)

    rendered_text = template.render(vars)
    with open(output_path, 'w') as f:
        f.write(rendered_text)

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
    mandatory = [group for group in KOLLA_MANDATORY_GROUPS if group not in roles.keys()]
    for group in mandatory: 
        inventory.append("[%s]" % (group))
    
    for role, nodes in roles.items():
        inventory.append("[%s]" % (role))
        inventory.extend(map(lambda n: "%s ansible_ssh_user=root g5k_role=%s" % (n.address, role), nodes))
    inventory.append("\n")
    return "\n".join(inventory)


if __name__ == "__main__":
    KollaG5k().start()
