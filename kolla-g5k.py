#! /usr/bin/env python
"""Kolla G5K: install OpenStack with Kolla over Grid'5000.

Usage:
  kolla-g5k.py [-h | --help] [-f CONFIG_PATH] [--force-deploy]
  kolla-g5k.py prepare-node [-f CONFIG_PATH] [--force-deploy] [-t TAGS | --tags=TAGS]
  kolla-g5k.py install-os [--reconfigure] [-t TAGS | --tags=TAGS]
  kolla-g5k.py init-os
  kolla-g5k.py bench TASK
  kolla-g5k.py ssh-tunnel
  kolla-g5k.py info

Options:
  -h --help           Show this help message.
  -f CONFIG_PATH      Path to the configuration file describing the
                      Grid'5000 deployment [default: ./reservation.yaml].
  -t TAGS --tags=TAGS Only run ansible tasks tagged with these values.
  --force-deploy      Force deployment.
  --reconfigure   Reconfigure the services after a deployment.

Commands:
  prepare-node  Make a G5K reservation and install the docker registry
  install-os    Run kolla and install OpenStack
  bench         Run rally on this OpenStack
  ssh-tunnel    Print configuration for port forwarding with horizon
  info          Show information of the actual deployment
"""
from docopt import docopt
from subprocess import call
import pickle
import requests
import pprint
from operator import itemgetter, attrgetter

from keystoneauth1.identity import v3
from keystoneauth1 import session
from glanceclient import client as gclient
from keystoneclient.v3 import client as kclient

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

# State of the script
STATE = {
    'config' : {}, # The config
    'config_file' : '', # The initial config file
    'nodes'  : {}, # Roles with nodes
    'phase'  : '', # Last phase that have been run
    'user'   : ''  # User id for this job
}

def save_state():
    state_path = os.path.join(SYMLINK_NAME, '.state')
    with open(state_path, 'wb') as state_file:
        pickle.dump(STATE, state_file)

def load_state():
    state_path = os.path.join(SYMLINK_NAME, '.state')
    if os.path.isfile(state_path):
        with open(state_path, 'rb') as state_file:
            STATE.update(pickle.load(state_file))

def update_config_state():
    """
    Update STATE['config'] with the config file options
    """
    config_file = STATE['config_file']
    with open(config_file, 'r') as f:
        STATE['config'].update(yaml.load(f))
    logger.info("Reloaded config %s", STATE['config'] )


def run_ansible(playbooks, inventory_path, extra_vars={}, tags=None):
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
            only_tags=tags,
            runner_callbacks=
              ansible.callbacks.PlaybookRunnerCallbacks(stats, verbose=1)
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
    call("cp %s/passwords.yml %s" % (TEMPLATE_DIR, passwords_path), shell=True)
    logger.info("Password file is copied to  %s" % (passwords_path))

    # admin openrc
    admin_openrc_path = os.path.join(directory, 'admin-openrc')
    admin_openrc_vars = {
        'keystone_address': kolla_vars['kolla_internal_vip_address']
    }
    render_template('templates/admin-openrc.jinja2', admin_openrc_vars, admin_openrc_path)
    logger.info("admin-openrc generated in %s" % (admin_openrc_path))


def prepare_node(conf_file, force_deploy, tags):
    g5k = G5kEngine(conf_file, force_deploy)

    g5k.start(args=[])

    STATE['config'].update(g5k.load())

    g5k.get_job()

    deployed, undeployed = g5k.deploy()
    if len(undeployed) > 0:
        sys.exit(31)

    roles = g5k.build_roles()

    # Get an IP for
    # kolla (haproxy)
    # docker registry
    # influx db
    # grafana
    vip_addresses = g5k.get_free_ip(4)
    # Get the NIC devices of the reserved cluster
    # XXX: this only works if all nodes are on the same cluster,
    # or if nodes from different clusters have the same devices
    interfaces = g5k.get_cluster_nics(STATE['config']['resources'].keys()[0])

    g5k.exec_command_on_nodes(
        g5k.deployed_nodes,
        'apt-get update && apt-get -y --force-yes install apt-transport-https',
        'Installing apt-transport-https...')

    # Install python on the nodes
    g5k.exec_command_on_nodes(
        g5k.deployed_nodes,
        'apt-get -y install python',
        'Installing Python on all the nodes...')

    # Generates files for ansible/kolla
    inventory_path = os.path.join(g5k.result_dir, 'multinode')
    base_inventory = STATE['config']['inventory']
    generate_inventory(roles, base_inventory, inventory_path)

    # Symlink current directory
    link = os.path.abspath(SYMLINK_NAME)
    try:
        os.remove(link)
    except OSError:
        pass
    os.symlink(g5k.result_dir, link)
    logger.info("Symlinked %s to %s" % (g5k.result_dir, link))

    STATE['config'].update({
        'vip': str(vip_addresses[0]),
        'registry_vip': str(vip_addresses[1]),
        'influx_vip': str(vip_addresses[2]),
        'grafana_vip': str(vip_addresses[3]),
        'network_interface': str(interfaces[0])
    })

    # Run the Ansible playbooks
    playbook_path = os.path.join(SCRIPT_PATH, 'ansible', 'prepare-node.yml')
    inventory_path = os.path.join(SYMLINK_NAME, 'multinode')
    run_ansible([playbook_path], inventory_path, STATE['config'], tags)

    kolla_vars = {
        'kolla_internal_vip_address' : str(vip_addresses[0]),
        'network_interface'          : str(interfaces[0]),
        'neutron_external_interface' : str(interfaces[1])
    }
    # Generating Ansible globals.yml, passwords.yml
    generate_kolla_files(g5k.config["kolla"], kolla_vars, g5k.result_dir)

    # Fills the state and save it in the `current` directory
    # TODO: Manage STATE at __main__ level
    STATE['config_file'] = conf_file
    STATE['nodes']  = roles
    STATE['user']   = g5k.user

def install_os(reconfigure, tags = None):
    update_config_state()

    # Clone or pull Kolla
    if os.path.isdir('kolla'):
        logger.info("Remove previous Kolla installation")
        kolla_path = os.path.join(SCRIPT_PATH, "kolla")
        call("rm -rf %s" % kolla_path, shell=True)

    logger.info("Cloning Kolla")
    call("cd %s ; git clone %s -b %s > /dev/null" % (SCRIPT_PATH, KOLLA_REPO, KOLLA_BRANCH), shell=True)
    
    logger.warning("Patching kolla, this should be \
            deprecated with the new version of Kolla")

    playbook = os.path.join(SCRIPT_PATH, "ansible/patches.yml")
    inventory_path = os.path.join(SYMLINK_NAME, 'multinode')
    run_ansible([playbook], inventory_path, STATE['config'])
   
    kolla_cmd = [os.path.join(SCRIPT_PATH, "kolla", "tools", "kolla-ansible")]

    if reconfigure:
        kolla_cmd.append('reconfigure')
    else:
        kolla_cmd.append('deploy')

    kolla_cmd.extend(["-i", "%s/multinode" % SYMLINK_NAME,
                  "--configdir", "%s" % SYMLINK_NAME])
    
    if tags is not None:
        kolla_cmd.extend(["--tags", args])

    call(kolla_cmd) 
   

def init_os():
    # Authenticate to keystone
    # http://docs.openstack.org/developer/keystoneauth/using-sessions.html
    # http://docs.openstack.org/developer/python-glanceclient/apiv2.html
    keystone_addr = STATE['config']['vip']
    auth = v3.Password(auth_url='http://%s:5000/v3' % keystone_addr,
                       username='admin',
                       password='demo',
                       project_name='admin',
                       user_domain_id='Default',
                       project_domain_id='default')
    sess = session.Session(auth=auth)

    # Install `member` role
    keystone = kclient.Client(session=sess)
    role_name = 'member'
    if role_name not in map(attrgetter('name'), keystone.roles.list()):
        logger.info("Creating role %s" % role_name)
        keystone.roles.create(role_name)

    # Install cirros with glance client if absent
    glance = gclient.Client('2', session=sess)
    cirros_name = 'cirros.uec'
    if cirros_name not in map(itemgetter('name'), glance.images.list()):
        # Download cirros
        image_url  = 'http://download.cirros-cloud.net/0.3.4/'
        image_name = 'cirros-0.3.4-x86_64-disk.img'
        logger.info("Downloading %s at %s..." % (cirros_name, image_url))
        cirros_img = requests.get(image_url + '/' + image_name)

        # Install cirros
        cirros = glance.images.create(name=cirros_name,
                                      container_format='bare',
                                      disk_format='qcow2',
                                      visibility='public')
        glance.images.upload(cirros.id, cirros_img.content)
        logger.info("%s has been created on OpenStack" %  cirros_name)

def bench(task):
    playbook_path = os.path.join(SCRIPT_PATH, 'ansible', 'run-bench.yml')
    inventory_path = os.path.join(SYMLINK_NAME, 'multinode')
    STATE['config']['task'] = task
    run_ansible([playbook_path], inventory_path, STATE['config'])

def ssh_tunnel():
    user = STATE['user']
    internal_vip_address = STATE['config']['vip']

    logger.info("ssh tunnel informations:")
    logger.info("___")

    script = "cat > /tmp/openstack_ssh_config <<EOF\n"
    script += "Host *.grid5000.fr\n"
    script += "  User " + user + " \n"
    script += "  ProxyCommand ssh -q " + user + "@194.254.60.4 nc -w1 %h %p # Access South\n"
    script += "EOF\n"

    port = 8080
    script += "ssh -F /tmp/openstack_ssh_config -N -L " + \
              str(port) + ":" + internal_vip_address + ":80 " + \
              user + "@access.grid5000.fr &\n"

    script += "echo 'http://localhost:8080'\n"

    logger.info(script)
    logger.info("___")


if __name__ == "__main__":
    args = docopt(__doc__)

    load_state()

    # If the user doesn't specify a phase in particular, then run all
    if not args['prepare-node'] and \
       not args['install-os'] and \
       not args['init-os'] and \
       not args['bench'] and \
       not args['ssh-tunnel'] and \
       not args['info']:
       args['prepare-node'] = True
       args['install-os'] = True
       args['init-os'] = True

    # Prepare node phase
    if args['prepare-node']:
        STATE['phase'] = 'prepare-node'
        config_file = args['-f']
        force_deploy = args['--force-deploy']
        tags = args['--tags'].split(',') if args['--tags'] else None
        prepare_node(config_file, force_deploy, tags)
        save_state()

    # Run kolla phase
    if args['install-os']:
        STATE['phase'] = 'install-os'
        install_os(args['--reconfigure'], args['--tags'])
        save_state()

    # Run init phase
    if args['init-os']:
        STATE['phase'] = 'init-os'
        init_os()
        save_state()

    # Run bench phase
    if args['bench']:
        STATE['phase'] = 'run-bench'
        bench(os.path.join(SCRIPT_PATH, args['TASK']))
        save_state()

    # Print information for port forwarding
    if args['ssh-tunnel']:
        ssh_tunnel()

    # Show info
    if args ['info']:
        pprint.pprint(STATE)
