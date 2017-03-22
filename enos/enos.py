# -*- coding: utf-8 -*-
"""Enos: Monitor and test your OpenStack.

usage: enos <command> [<args> ...] [-e ENV|--env=ENV]
            [-h|--help] [-v|--version] [-s|--silent|--vv]

General options:
  -e ENV --env=ENV  Path to the environment directory. You should
                    use this option when you want to link to a specific
                    experiment. Not specifying this value will
                    discard the loading of the environment (it
                    makes sense for `up`).
  -h --help         Show this help message.
  -s --silent       Quiet mode.
  -v --version      Show version number.
  -vv               Verbose mode.

Commands:
  up             Get resources and install the docker registry.
  os             Run kolla and install OpenStack.
  init           Initialise OpenStack with the bare necessities.
  bench          Run rally on this OpenStack.
  backup         Backup the environment
  ssh-tunnel     Print configuration for port forwarding with horizon.
  tc             Enforce network constraints
  info           Show information of the actual deployment.
  destroy        Destroy the resources used by the deployment
  deploy         Shortcut for enos up, then enos os and enos config.

See 'enos <command> --help' for more information on a specific
command.

"""
from utils.constants import (SYMLINK_NAME, TEMPLATE_DIR, ANSIBLE_DIR,
                             NETWORK_IFACE, EXTERNAL_IFACE, VERSION)
from utils.extra import (run_ansible, generate_inventory,
                         generate_kolla_files, to_abs_path, pop_ip,
                         make_provider)

from utils.network_constraints import (build_grp_constraints,
                                       build_ip_constraints)
from utils.enostask import enostask

from datetime import datetime
import logging

from docopt import docopt
import pprint

import os
import sys
from subprocess import call

import yaml
import itertools

CALL_PATH = os.getcwd()


@enostask("""
usage: enos up  [-e ENV|--env=ENV][-f CONFIG_PATH] [--force-deploy]
                [-t TAGS|--tags=TAGS] [-s|--silent|-vv]

Get resources and install the docker registry.

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link to a specific
                       experiment. Do not specify it in other cases.
  -f CONFIG_PATH       Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
  -h --help            Show this help message.
  --force-deploy       Force deployment [default: False].
  -s --silent          Quiet mode.
  -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
  -vv                  Verbose mode.

""")
def up(env=None, **kwargs):
    logging.debug('phase[up]: args=%s' % kwargs)

    # Generates a directory for results
    resultdir_name = kwargs['--env'] or \
            'enos_' + datetime.today().isoformat()

    resultdir = os.path.join(CALL_PATH, resultdir_name)
    # The result directory cannot be created if a related file exists
    if os.path.isfile(resultdir):
        logging.error("Result directory cannot be created due to %s" %
                resultdir)
        sys.exit(1)

    # Create the result directory if it does not exist
    os.path.isdir(resultdir) or os.mkdir(resultdir)
    logging.info('Generate results in %s' % resultdir)
    env['resultdir'] = resultdir

    # Symlink the result directory with the current directory
    link = os.path.abspath(SYMLINK_NAME)

    os.path.lexists(link) and os.remove(link)
    try:
        os.symlink(env['resultdir'], link)
        logging.info("Symlinked %s to %s" % (env['resultdir'], link))
    except OSError:
        # An harmless error can occur due to a race condition when multiple
        # regions are simultaneously deployed
        logging.warning("Symlink %s to %s failed" %
                (env['resultdir'], link))
        pass

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
    provider = make_provider(env)
    rsc, provider_net, eths = \
        provider.init(env['config'], CALL_PATH, kwargs['--force-deploy'])

    env['rsc'] = rsc
    env['provider_net'] = provider_net
    env['eths'] = eths

    # Generates inventory for ansible/kolla
    base_inventory = env['config']['inventory']
    inventory = os.path.join(env['resultdir'], 'multinode')
    generate_inventory(env['rsc'], base_inventory, inventory)
    logging.info('Generates inventory %s' % inventory)

    env['inventory'] = inventory

    # Set variables required by playbooks of the application
    vip = pop_ip(env)
    env['config'].update({
        # Enos specific
        'vip':          vip,
        'registry_vip': pop_ip(env),
        'influx_vip':   pop_ip(env),
        'grafana_vip':  pop_ip(env),
        'network_interface': eths[NETWORK_IFACE],
        'resultdir':    env['resultdir']
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


@enostask("""
usage: enos os [-e ENV|--env=ENV] [--reconfigure] [-t TAGS|--tags=TAGS]
               [-s|--silent|-vv]

Run kolla and install OpenStack.

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  --reconfigure        Reconfigure the services after a deployment.
  -s --silent          Quiet mode.
  -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
  -vv                  Verbose mode.
""" % SYMLINK_NAME)
def install_os(env=None, **kwargs):
    logging.debug('phase[os]: args=%s' % kwargs)

    # Generates kolla globals.yml, passwords.yml
    generated_kolla_vars = {
        'neutron_external_address':   pop_ip(env),
        'network_interface':          env['eths'][NETWORK_IFACE],
        'kolla_internal_vip_address': env['config']['vip'],
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
    call("git clone %s --branch %s --single-branch --quiet %s" %
            (env['config']['kolla_repo'],
             env['config']['kolla_ref'],
             kolla_path),
         shell=True)

    logging.warning(("Patching kolla, this should be ",
                     "deprecated with the new version of Kolla"))

    playbook = os.path.join(ANSIBLE_DIR, "patches.yml")
    run_ansible([playbook], env['inventory'], env['config'])

    kolla_cmd = [os.path.join(kolla_path, "tools", "kolla-ansible")]

    if kwargs['--reconfigure']:
        kolla_cmd.append('reconfigure')
    else:
        kolla_cmd.append('deploy')

    kolla_cmd.extend(["-i", "%s/multinode" % env['resultdir'],
                      "--passwords", "%s/passwords.yml" % env['resultdir'],
                      "--configdir", "%s" % env['resultdir']])

    if kwargs['--tags']:
        kolla_cmd.extend(['--tags', kwargs['--tags']])

    call(kolla_cmd)


@enostask("""
usage: enos init [-e ENV|--env=ENV] [-s|--silent|-vv]

Initialise OpenStack with the bare necessities:
- Install a 'member' role
- Download and install a cirros image
- Install default flavor (m1.tiny, ..., m1.xlarge)
- Install default network

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  -s --silent          Quiet mode.
  -vv                  Verbose mode.
""" % SYMLINK_NAME)
def init_os(env=None, **kwargs):
    logging.debug('phase[init]: args=%s' % kwargs)

    cmd = []
    cmd.append('. %s' % os.path.join(env['resultdir'], 'admin-openrc'))
    # add cirros image
    images = [{'name': 'cirros.uec',
               'url': 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img'}]
    for image in images:
        cmd.append("wget -q -O /tmp/%s %s" % (image['name'], image['url']))
        cmd.append("openstack image create"
                   " --disk-format=qcow2"
                   " --container-format=bare"
                   " --property architecture=x86_64"
                   " --public"
                   " --file /tmp/%s"
                   " %s" % (image['name'], image['name']))

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
        cmd.append("openstack flavor create %s"
                   " --id auto"
                   " --ram %s"
                   " --disk %s"
                   " --vcpus %s"
                   " --public" % (flavor[0], flavor[1], flavor[2], flavor[3]))

    # security groups - allow everything
    protos = ['icmp', 'tcp', 'udp']
    for proto in protos:
        cmd.append("openstack security group rule create default"
                   " --protocol %s"
                   " --dst-port 1:65535"
                   " --src-ip 0.0.0.0/0" % proto)

    # quotas - set some unlimited for admin project
    quotas = ['cores', 'ram', 'instances']
    for quota in quotas:
        cmd.append('nova quota-class-update --%s -1 default' % quota)

    quotas = ['fixed-ips', 'floating-ips']
    for quota in quotas:
        cmd.append('openstack quota set --%s -1 admin' % quota)

    # default network (one public/one private)
    cmd.append("openstack network create public"
               " --share"
               " --provider-physical-network physnet1"
               " --provider-network-type flat"
               " --external")

    cmd.append("openstack subnet create public-subnet"
               " --network public"
               " --subnet-range %s"
               " --no-dhcp"
               " --allocation-pool start=%s,end=%s"
               " --gateway %s"
               " --dns-nameserver %s"
               " --ip-version 4" % (
                   env['provider_net']['cidr'],
                   env['provider_net']['start'],
                   env['provider_net']['end'],
                   env['provider_net']['gateway'],
                   env['provider_net']['dns']))

    cmd.append("openstack network create private"
               " --provider-network-type vxlan")

    cmd.append("openstack subnet create private-subnet"
               " --network private"
               " --subnet-range 192.168.0.0/18"
               " --gateway 192.168.0.1"
               " --dns-nameserver %s"
               " --ip-version 4" % (env["provider_net"]['dns']))

    # create a router between this two networks
    cmd.append('openstack router create router')
    # NOTE(msimonin): not sure how to handle these 2 with openstack cli
    cmd.append('neutron router-gateway-set router public')
    cmd.append('neutron router-interface-add router private-subnet')

    cmd = '\n'.join(cmd)

    logging.info(cmd)
    call(cmd, shell=True)


@enostask("""
usage: enos bench [-e ENV|--env=ENV] [-s|--silent|-vv] (--workload=WORKLOAD)

Run rally on this OpenStack.

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  -s --silent          Quiet mode.
  -vv                  Verbose mode.
  --workload=WORKLOAD  Path to the workload directory.
                       This directory must contain a run.yml file
                       that contains the description of the different
                       scenarios to launch.
""" % SYMLINK_NAME)
def bench(env=None, **kwargs):
    def cartesian(d):
        """returns the cartesian product of the args."""
        logging.debug(d)
        f = []
        for k, v in d.items():
            if isinstance(v, list):
                f.extend([[[k, vv] for vv in v]])
            else:
                f.append([[k, v]])
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
                    playbook_path = os.path.join(ANSIBLE_DIR,
                            'run-bench.yml')
                    inventory_path = os.path.join(env['resultdir'],
                            'multinode')
                    # NOTE(msimonin) all the scenarios must reside on
                    # the workload directory
                    env['config']['bench'] = {
                        'type': bench_type,
                        'location': os.path.abspath(
                                      os.path.join(workload_dir,
                                                   scenario["file"])),
                        'file': scenario["file"],
                        'args': a
                    }
                    run_ansible([playbook_path], inventory_path, env['config'])


@enostask("""
usage: enos backup [--backup_dir=BACKUP_DIR] [-e ENV|--env=ENV]
                   [-s|--silent|-vv]

Backup the environment

Options:
  --backup_dir=BACKUP_DIR  Backup directory.
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  -s --silent          Quiet mode.
  -vv                  Verbose mode.
""" % SYMLINK_NAME)
def backup(env=None, **kwargs):

    backup_dir = kwargs['--backup_dir'] \
            or kwargs['--env'] \
            or SYMLINK_NAME

    backup_dir = to_abs_path(backup_dir)
    # create if necessary
    if not os.path.isdir(backup_dir):
        os.mkdir(backup_dir)
    # update the env
    env['config']['backup_dir'] = backup_dir
    playbook_path = os.path.join(ANSIBLE_DIR, 'backup.yml')
    inventory_path = os.path.join(env['resultdir'], 'multinode')
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


@enostask("""
usage: enos tc [-e ENV|--env=ENV] [--test] [-s|--silent|-vv]

Enforce network constraints

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  -s --silent          Quiet mode.
  --test               Test the rules by generating various reports.
  -vv                  Verbose mode.
""" % SYMLINK_NAME)
def tc(env=None, **kwargs):
    """
    Enforce network constraints
    1) Retrieve the list of ips for all nodes (ansible)
    2) Build all the constraints (python)
        {source:src, target: ip_dest, device: if, rate:x,  delay:y}
    3) Enforce those constraints (ansible)
    """
    test = kwargs['--test']
    if test:
        logging.info('Checking the constraints')
        utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
        options = {
                'action': 'test',
                'tc_output_dir': env['resultdir'],
                # NOTE(msimonin): we retrieve eth name from the env instead
                # of env['config'] in case os hasn't been called
                'network_interface': env['eths'][NETWORK_IFACE]
                }
        run_ansible([utils_playbook], env['inventory'], options)
        return

    # 1. getting  ips/devices information
    logging.info('Getting the ips of all nodes')
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    ips_file = os.path.join(env['resultdir'], 'ips.txt')
    options = {
            'action': 'ips',
            'ips_file': ips_file,
            # NOTE(msimonin): we retrieve eth name from the env instead
            # of env['config'] in case os hasn't been called
            'network_interface': env['eths'][NETWORK_IFACE],
            'neutron_external_interface': env['eths'][EXTERNAL_IFACE]
    }
    run_ansible([utils_playbook], env['inventory'], options)

    # 2.a building the group constraints
    logging.info('Building all the constraints')
    topology = env['config']['topology']
    network_constraints = env['config']['network_constraints']
    constraints = build_grp_constraints(topology, network_constraints)
    # 2.b Building the ip/device level constaints
    with open(ips_file) as f:
        ips = yaml.load(f)
        # will hold every single constraint
        ips_with_constraints = build_ip_constraints(env['rsc'],
                                                    ips,
                                                    constraints)
        # dumping it for debugging purpose
        ips_with_constraints_file = os.path.join(env['resultdir'],
                                                 'ips_with_constraints.yml')
        with open(ips_with_constraints_file, 'w') as g:
            yaml.dump(ips_with_constraints, g)

    # 3. Enforcing those constraints
    logging.info('Enforcing the constraints')
    # enabling/disabling network constraints
    enable = network_constraints.setdefault('enable', True)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {
        'action': 'tc',
        'ips_with_constraints': ips_with_constraints,
        'tc_enable': enable,
    }
    run_ansible([utils_playbook], env['inventory'], options)


@enostask("""
usage: enos info [-e ENV|--env=ENV]


Show information of the `ENV` deployment.

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
""" % SYMLINK_NAME)
def info(env=None, **kwargs):
    pprint.pprint(env)


@enostask("""
usage: enos destroy [-e ENV|--env=ENV] [-s|--silent|-vv]

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment [default: %s].
  -h --help            Show this help message.
  -s --silent          Quiet mode.
  -vv                  Verbose mode.
""" % SYMLINK_NAME)
def destroy(env=None, **kwargs):
    provider = make_provider(env)
    provider.destroy(CALL_PATH, env)


@enostask("""
usage: enos deploy [-e ENV|--env=ENV] [-f CONFIG_PATH] [--force-deploy]
                   [-s|--silent|-vv]

Shortcut for enos up, then enos os, and finally enos config.

Options:
  -e ENV --env=ENV     Path to the environment directory. You should
                       use this option when you want to link a specific
                       experiment.
  -f CONFIG_PATH       Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
  --force-deploy       Force deployment [default: False].
  -s --silent          Quiet mode.
  -vv                  Verbose mode.
""")
def deploy(**kwargs):
    # --reconfigure and --tags can not be provided in 'deploy'
    # but they are required for 'up' and 'install_os'
    kwargs['--reconfigure'] = False
    kwargs['--tags'] = None

    up(**kwargs)

    # If the user doesn't specify an experiment, then set the ENV directory to
    # the default one.
    if not kwargs['--env']:
        kwargs['--env'] = SYMLINK_NAME

    install_os(**kwargs)
    init_os(**kwargs)


def main():
    args = docopt(__doc__,
                  version=VERSION,
                  options_first=True)

    if '-vv' in args['<args>']:
        logging.basicConfig(level=logging.DEBUG)
        args['<args>'].remove('-vv')
    elif '-s' in args['<args>']:
        logging.basicConfig(level=logging.ERROR)
        args['<args>'].remove('-s')
    elif '--silent' in args['<args>']:
        logging.basicConfig(level=logging.ERROR)
        args['<args>'].remove('--silent')
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
    elif args['<command>'] == 'tc':
        tc(**docopt(tc.__doc__, argv=argv))
    elif args['<command>'] == 'info':
        info(**docopt(info.__doc__, argv=argv))
    elif args['<command>'] == 'destroy':
        destroy(**docopt(destroy.__doc__, argv=argv))
    else:
        pass


if __name__ == '__main__':
    main()
