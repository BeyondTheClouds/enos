# -*- coding: utf-8 -*-
"""Enos: Monitor and test your OpenStack.

usage: enos <command> [<args> ...] [-h|--help]
            [-v|--version] [-vv|-s|--silent]

Options:
  -h --help      Show this help message.
  -v --version   Show version number.
  -vv            Verbose mode.
  -s --silent    Quiet mode.

Commands:
  up             Get resources and install the docker registry.
  os             Run kolla and install OpenStack.
  init           Initialise OpenStack with the bare necessities.
  bench          Run rally on this OpenStack.
  backup         Backup the environment
  ssh-tunnel     Print configuration for port forwarding with horizon.
  info           Show information of the actual deployment.
  deploy         Shortcut for enos up, then enos os and enos config.

See 'enos <command> --help' for more information on a specific
command.

"""
from utils.constants import (SYMLINK_NAME, TEMPLATE_DIR, ANSIBLE_DIR,
                             INTERNAL_IP, REGISTRY_IP, INFLUX_IP,
                             GRAFANA_IP, NEUTRON_IP, NETWORK_IFACE,
                             EXTERNAL_IFACE, VERSION)
from utils.extra import (run_ansible, generate_inventory,
                         generate_kolla_files, to_abs_path)
from utils.enostask import enostask

from datetime import datetime
import logging

from docopt import docopt
import pprint
from operator import itemgetter, attrgetter

import os
import sys
from subprocess import call

import yaml
import json
import itertools

CALL_PATH = os.getcwd()


@enostask("""
usage: enos up [-f CONFIG_PATH] [--force-deploy] [-t TAGS | --tags=TAGS]
               [--provider=PROVIDER] [-vv|-s|--silent]

Get resources and install the docker registry.

Options:
  -h --help            Show this help message.
  -f CONFIG_PATH       Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
  --force-deploy       Force deployment [default: False].
  -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
  --provider=PROVIDER  The provider name [default: G5K].

""")
def up(provider=None, env=None, **kwargs):
    logging.debug('phase[up]: args=%s' % kwargs)

    # Loads the configuration file
    config_file = kwargs['-f']
    if os.path.isfile(config_file):
        env['config_file'] = config_file
        with open(config_file, 'r') as f:
            env['config'].update(yaml.load(f))
            logging.info("Reloaded config %s", env['config'])
    else:
        logging.error('Configuration file %s does not exist', config_file)
        sys.exit(1)

    # Calls the provider and initialise resources
    rsc, ips, eths, provider_network = provider.init(env['config'], kwargs['--force-deploy'])

    env['rsc'] = rsc
    env['ips'] = ips
    env['eths'] = eths
    env['provider_network'] = provider_network

    # Generates a directory for results
    resultdir_name = 'enos_' + datetime.today().isoformat()
    resultdir = os.path.join(CALL_PATH, resultdir_name)
    os.mkdir(resultdir)
    logging.info('Generates result directory %s' % resultdir_name)

    env['resultdir'] = resultdir

    # Generates inventory for ansible/kolla
    base_inventory = env['config']['inventory']
    inventory = os.path.join(resultdir, 'multinode')
    generate_inventory(env['rsc'], base_inventory, inventory)
    logging.info('Generates inventory %s' % inventory)

    env['inventory'] = inventory

    # Set variables required by playbooks of the application
    env['config'].update({
        # Enos specific
        'vip':          ips[INTERNAL_IP],
        'registry_vip': ips[REGISTRY_IP],
        'influx_vip':   ips[INFLUX_IP],
        'grafana_vip':  ips[GRAFANA_IP],

        # Kolla + common specific
        'neutron_external_address': ips[NEUTRON_IP],
        'network_interface':        eths[NETWORK_IFACE],

        # Kolla specific
        'kolla_internal_vip_address': ips[INTERNAL_IP],
        'neutron_external_interface': eths[EXTERNAL_IFACE]
    })
    passwords = os.path.join(TEMPLATE_DIR, "passwords.yml")
    with open(passwords) as f:
        env['config'].update(yaml.load(f))

    # Executes hooks and runs playbook that initializes resources (eg,
    # installs the registry, install monitoring tools, ...)
    provider.before_preintsall(env)
    up_playbook = os.path.join(ANSIBLE_DIR, 'up.yml')
    run_ansible([up_playbook], inventory, env['config'], kwargs['--tags'])
    provider.after_preintsall(env)

    # Symlink current directory
    link = os.path.abspath(SYMLINK_NAME)
    try:
        os.remove(link)
    except OSError:
        pass
    os.symlink(resultdir, link)
    logging.info("Symlinked %s to %s" % (resultdir, link))


@enostask("""
usage: enos os [--reconfigure] [-t TAGS | --tags=TAGS] [-vv|-s|--silent]

Run kolla and install OpenStack.

Options:
  -h --help            Show this help message.
  -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
  --reconfigure        Reconfigure the services after a deployment.
""")
def install_os(env=None, **kwargs):
    logging.debug('phase[os]: args=%s' % kwargs)
    # Generates kolla globals.yml, passwords.yml
    generated_kolla_vars = {
        # Kolla + common specific
        'neutron_external_address':   env['ips'][NEUTRON_IP],
        'network_interface':          env['eths'][NETWORK_IFACE],
        # Kolla specific
        'kolla_internal_vip_address': env['ips'][INTERNAL_IP],
        'neutron_external_interface': env['eths'][EXTERNAL_IFACE]
    }
    generate_kolla_files(env['config']["kolla"],
                         generated_kolla_vars,
                         env['resultdir'])

    # Clone or pull Kolla
    kolla_path = os.path.join(env['resultdir'], 'kolla')
    if os.path.isdir(kolla_path):
        logging.info("Remove previous Kolla installation")
        call("rm -rf %s" % kolla_path, shell=True)

    logging.info("Cloning Kolla")
    call("git clone %s -b %s %s > /dev/null" % (env['kolla_repo'],
                                                env['kolla_branch'],
                                                kolla_path), shell=True)

    logging.warning(("Patching kolla, this should be ",
                     "deprecated with the new version of Kolla"))

    playbook = os.path.join(ANSIBLE_DIR, "patches.yml")
    run_ansible([playbook], env['inventory'], env['config'])

    kolla_cmd = [os.path.join(kolla_path, "tools", "kolla-ansible")]

    if kwargs['--reconfigure']:
        kolla_cmd.append('reconfigure')
    else:
        kolla_cmd.append('deploy')

    kolla_cmd.extend(["-i", "%s/multinode" % SYMLINK_NAME,
                      "--passwords", "%s/passwords.yml" % SYMLINK_NAME,
                      "--configdir", "%s" % SYMLINK_NAME])

    if kwargs['--tags']:
        kolla_cmd.extend(['--tags', kwargs['--tags']])

    call(kolla_cmd)


@enostask("""
usage: enos init [-vv|-s|--silent]

Initialise OpenStack with the bare necessities:
- Install a 'member' role
- Download and install a cirros image
- Install default flavor (m1.tiny, ..., m1.xlarge)
- Install default network

Options:
  -h --help            Show this help message.
""")
def init_os(env=None, **kwargs):
    logging.debug('phase[init]: args=%s' % kwargs)
    cmd = ['source %s' % os.path.join(SYMLINK_NAME, 'admin-openrc')]
    # add cirros image
    images = [{'name': 'cirros.uec', 'url':'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img'}] 
    for image in images:
        cmd.append("/usr/bin/wget -q -O /tmp/%s %s" % (image['name'], image['url']))
        cmd.append('openstack image create' \
                ' --disk-format=qcow2' \
                ' --container-format=bare' \
                ' --property architecture=x86_64' \
                ' --public' \
                ' --file /tmp/%s' \
                ' %s' % (image['name'], image['name']))

    # flavors
    flavors = [
            # name, ram, disk, vcpus
            ('m1.tiny', 512, 1, 1),
            ('m1.small', 2048, 20, 1),
            ('m1.medium', 4096, 40, 2),
            ('m1.large', 8192, 80, 4),
            ('m1.xlarge', 16384, 160, 8)
    ]
    for flavor in flavors:
        cmd.append('openstack flavor create %s' \
                ' --id auto' \
                ' --ram %s' \
                ' --disk %s' \
                ' --vcpus %s' \
                ' --public' % (flavor[0], flavor[1], flavor[2], flavor[3]))

    # security groups - allow everything 
    protos = ['icmp', 'tcp', 'udp']
    for proto in protos:
        cmd.append('openstack security group rule create default' \
                ' --protocol %s' \
                ' --dst-port 1:65535' \
                ' --src-ip 0.0.0.0/0' % proto)
    
    # quotas - set some unlimited for admin project
    quotas = ['cores', 'ram', 'instances']
    for quota in quotas:
        cmd.append('nova quota-class-update --%s -1 default' % quota)

    quotas = ['fixed-ips', 'floating-ips']
    for quota in quotas:
        cmd.append('openstack quota set --%s -1 admin' % quota)

    # default network (one public / one provite)
    cmd.append('openstack network create public' \
            ' --share' \
            ' --provider-physical-network physnet1' \
            ' --provider-network-type flat' \
            ' --external')
    cmd.append('openstack subnet create public-subnet' \
            ' --network public' \
            ' --subnet-range %s' \
            ' --no-dhcp'
            ' --allocation-pool start=%s,end=%s' \
            ' --gateway %s' \
            ' --ip-version 4' % (
                env["provider_network"]['cidr'],
                env["provider_network"]['start'],
                env["provider_network"]['end'],
                env["provider_network"]['gateway'])
            )
    cmd.append('openstack network create private' \
            ' --provider-network-type vxlan')

    cmd.append('openstack subnet create private-subnet' \
            ' --network private' \
            ' --subnet-range 192.168.0.0/18' \
            ' --gateway 192.168.0.1' \
            ' --dns-nameserver %s' \
            ' --ip-version 4' % (
                env["provider_network"]['dns'])
            )
    # create a router between this two networks
    cmd.append('openstack router create router')
    # NOTE(msimonin): not sure how to handle these 2 with openstack cli 
    cmd.append('neutron router-gateway-set router public')
    cmd.append('neutron router-interface-add router private-subnet')

    cmd = '\n'.join(cmd)
    print(cmd)
    call(cmd, shell = True)


@enostask("""
usage: enos bench [--workload=WORKLOAD]
                  [-vv|-s|--silent]

Run rally on this OpenStack.

Options:
  -h --help                 Show this help message.
  --workload=WORKLOAD       Path to the workload directory.
                            This directory must contain a run.yml file
                            that contains the description of the different
                            scenarios to launch
""")
def bench(env=None, **kwargs):
    def cartesian(d):
        """returns the cartesian product of the args."""
        logging.debug(d)
        f = []
        for k, v in d.items():
            if isinstance(v, list):
              f.extend([[[k, vv] for vv in v]])
            else:
              f.append([[k,v]])
        logging.debug(f)
        product = []
        for e in itertools.product(*f):
            product.append(dict(e))
        return product

    logging.debug('phase[bench]: args=%s' % kwargs)
    workload_dir = kwargs["--workload"]
    with open(os.path.join(workload_dir, "run.yml")) as workload_f:
        workload = yaml.load(workload_f)
        for bench_type, desc in workload.items():
            scenarios = desc.get("scenarios", [])
            for scenario in scenarios:
                # merging args 
                top_args = desc.get("args", {})
                args = scenario.get("args", {})
                top_args.update(args)
                # merging enabled, skipping if not enabled
                top_enabled = desc.get("enabled", True)
                enabled = scenario.get("enabled", True)
                if not (top_enabled and enabled):
                    continue
                for a in cartesian(top_args):
                    playbook_path = os.path.join(ANSIBLE_DIR, 'run-bench.yml')
                    inventory_path = os.path.join(SYMLINK_NAME, 'multinode')
                    # NOTE(msimonin) all the scenarios must reside on the workload directory
                    env['config']['bench'] = {
                        'type': bench_type,
                        'location': os.path.abspath(os.path.join(workload_dir, scenario["file"])),
                        'args': a
                    }
                    run_ansible([playbook_path], inventory_path, env['config'])
    
@enostask("""
usage: enos backup [--backup_dir=BACKUP_DIR ] [-vv|-s|--silent]

Backup the environment

Options:
  --backup_dir=BACKUP_DIR   Backup directory.
  -h --help                 Show this help message.
""")
def backup(env = None, **kwargs):
    backup_dir = kwargs['--backup_dir']
    if backup_dir is None:
        backup_dir = SYMLINK_NAME

    backup_dir = to_abs_path(backup_dir)
    # create if necessary
    if not os.path.isdir(backup_dir):
        os.mkdir(backup_dir)
    # update the env
    env['config']['backup_dir'] = backup_dir
    playbook_path = os.path.join(ANSIBLE_DIR, 'backup.yml')
    inventory_path = os.path.join(SYMLINK_NAME, 'multinode')
    run_ansible([playbook_path], inventory_path, env['config'])


@enostask("""usage: enos ssh-tunnel""")
def ssh_tunnel(env=None, **kwargs):
    user = env['user']
    internal_vip_address = env['config']['vip']

    logging.info("ssh tunnel informations:")
    logging.info("___")

    script = "cat > /tmp/openstack_ssh_config <<EOF\n"
    script += "Host *.grid5000.fr\n"
    script += "  User " + user + " \n"
    script += "  ProxyCommand ssh -q " + user
    script += "@194.254.60.4 nc -w1 %h %p # Access South\n"
    script += "EOF\n"

    port = 8080
    script += "ssh -F /tmp/openstack_ssh_config -N -L " + \
              str(port) + ":" + internal_vip_address + ":80 " + \
              user + "@access.grid5000.fr &\n"

    script += "echo 'http://localhost:8080'\n"

    logging.info(script)
    logging.info("___")


@enostask("usage: enos info")
def info(env=None, **kwargs):
    pprint.pprint(env)


@enostask("""
usage: enos deploy [-f CONFIG_PATH] [--force-deploy]
                   [--provider=PROVIDER] [-t TAGS | --tags=TAGS]
                   [--reconfigure] [-vv|-s|--silent]

Shortcut for enos up, then enos os, and finally enos config.

Options:
  -h --help            Show this help message.
  -f CONFIG_PATH       Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
  --force-deploy       Force deployment [default: False].
  --provider=PROVIDER  The provider name [default: G5K].
""")
def deploy(**kwargs):
    up(**kwargs)
    install_os(**kwargs)
    init_os(**kwargs)


def main():
    args = docopt(__doc__,
                  version=VERSION,
                  options_first=True)

    if '-vv' in args['<args>']:
        logging.basicConfig(level=logging.DEBUG)
    elif '-s' in args['<args>'] or '--silent' in args['<args>']:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)

    argv = [args['<command>']] + args['<args>']

    if args['<command>'] == 'deploy':
        deploy(**docopt(deploy.__doc__, argv=argv))
    elif args['<command>'] == 'up':
        up(**docopt(up.__doc__, argv=argv))
    elif args['<command>'] == 'os':
        install_os(**docopt(install_os.__doc__, argv=argv))
    elif args['<command>'] == 'init':
        init_os(**docopt(init_os.__doc__, argv=argv))
    elif args['<command>'] == 'bench':
        bench(**docopt(bench.__doc__, argv=argv))
    elif args['<command>'] == 'backup':
        backup(**docopt(backup.__doc__, argv=argv))
    elif args['<command>'] == 'ssh-tunnel':
        ssh_tunnel(**docopt(ssh_tunnel.__doc__, argv=argv))
    elif args['<command>'] == 'info':
        info(**docopt(info.__doc__, argv=argv))
    else:
        pass

if __name__ == '__main__':
    main()
