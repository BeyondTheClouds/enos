# -*- coding: utf-8 -*-
from enoslib.task import enostask
from enoslib.api import run_ansible

from enos.utils.constants import (SYMLINK_NAME, ANSIBLE_DIR, INVENTORY_DIR,
                                  VERSION, NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE)
from enos.utils.errors import EnosFilePathError
from enos.utils.extra import (bootstrap_kolla, generate_inventory, pop_ip, make_provider,
                              mk_enos_values, load_config, seekpath, get_vip_pool, lookup_network,
                              in_kolla)
from enos.utils.network_constraints import (build_grp_constraints,
                                       build_ip_constraints)
from enos.utils.enostask import check_env

from datetime import datetime
import logging

from docopt import docopt
import pprint

import os
from subprocess import check_call

import json
import pickle
import yaml

import itertools
import operator

def get_and_bootstrap_kolla(env, force=False):
    """This gets kolla in the current directory.

    force iff a potential previous installation must be overwritten.
    """

    kolla_path = os.path.join(env['resultdir'], 'kolla')

    if force and os.path.isdir(kolla_path):
        logging.info("Remove previous Kolla installation")
        check_call("rm -rf %s" % kolla_path, shell=True)
    if not os.path.isdir(kolla_path):
        logging.info("Cloning Kolla repository...")
        check_call("git clone %s --branch %s --single-branch --quiet %s" %
                       (env['config']['kolla_repo'],
                        env['config']['kolla_ref'],
                        kolla_path),
                   shell=True)
        # Bootstrap kolla running by patching kolla sources (if any) and
        # generating admin-openrc, globals.yml, passwords.yml
        bootstrap_kolla(env)

        # Installing the kolla dependencies in the kolla venv
        in_kolla('cd %s && pip install .' % kolla_path)
        # Kolla recommends installing ansible manually.
        # Currently anything over 2.3.0 is supported, not sure about the future
        # So we hardcode the version to something reasonnable for now
        in_kolla('cd %s && pip install ansible==2.5.7' % kolla_path)

    return kolla_path


@enostask(new=True)
def up(config, config_file=None, env=None, **kwargs):
    logging.debug('phase[up]: args=%s' % kwargs)
    env['config'] = config
    env['config_file'] = config_file

    # Calls the provider and initialise resources
    provider = make_provider(env)

    #config = load_config(env['config'],
    #                     provider.topology_to_resources,
    #                     provider.default_config())
    # done by enoslib ar init + provider.dfefault_config()

    rsc, networks = \
        provider.init(env['config'], kwargs['--force-deploy'])

    env['rsc'] = rsc
    env['networks'] = networks

    logging.debug("Provider ressources: %s", env['rsc'])
    logging.debug("Provider network information: %s", env['networks'])

    # Generates inventory for ansible/kolla
    inventory = os.path.join(env['resultdir'], 'multinode')
    inventory_conf = env['config'].get('inventory')
    if not inventory_conf:
        logging.debug("No inventory specified, using the sample.")
        base_inventory = os.path.join(INVENTORY_DIR, 'inventory.sample')
    else:
        base_inventory = seekpath(inventory_conf)

    generate_inventory(env['rsc'], env['networks'], base_inventory, inventory)
    logging.info('Generates inventory %s' % inventory)

    env['inventory'] = inventory


    # Set variables required by playbooks of the application
    # https://github.com/BeyondTheClouds/enos/pull/159/files#diff-15a7159acfc2c0c18193258af93ad086R135

    vip_pool = get_vip_pool(networks)
    env['config'].update({
       'vip':               pop_ip(vip_pool),
       'registry_vip':      pop_ip(vip_pool),
       'influx_vip':        pop_ip(vip_pool),
       'grafana_vip':       pop_ip(vip_pool),
       'resultdir':         env['resultdir'],
       'rabbitmq_password': "demo",
       'database_password': "demo"
    })

    # Runs playbook that initializes resources (eg,
    # installs the registry, install monitoring tools, ...)
    up_playbook = os.path.join(ANSIBLE_DIR, 'up.yml')
    run_ansible([up_playbook], inventory, extra_vars=env['config'],
                tags=kwargs['--tags'])


@enostask()
@check_env
def install_os(env=None, **kwargs):
    logging.debug('phase[os]: args=%s' % kwargs)

    kolla_path = get_and_bootstrap_kolla(env, force=True)
    # Construct kolla-ansible command...
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

    logging.info("Calling Kolla...")

    in_kolla(kolla_cmd)


@enostask()
@check_env
def init_os(env=None, **kwargs):
    logging.debug('phase[init]: args=%s' % kwargs)
    # Images
    #images = [{'name': 'debian-9',
    #           'url':  ('https://cdimage.debian.org/cdimage/openstack/'
    #                    'current-9/debian-9-openstack-amd64.qcow2')},
    #          {'name': 'cirros.uec',
    #           'url':  ('http://download.cirros-cloud.net/'
    #                    '0.3.4/cirros-0.3.4-x86_64-disk.img')}]
    #for image in images:
    #    cmd.append("ls -l /tmp/%(name)s.qcow2 || "
    #               "curl -L -o /tmp/%(name)s.qcow2 %(url)s" % image)
    #    cmd.append("openstack image show %(name)s || "
    #               "openstack image create"
    #               " --disk-format=qcow2"
    #               " --container-format=bare"
    #               " --property architecture=x86_64"
    #               " --public"
    #               " --file /tmp/%(name)s.qcow2"
    #               " %(name)s" % image)
    playbook_values = mk_enos_values(env)
    playbook_path = os.path.join(ANSIBLE_DIR, 'init_os.yml')
    inventory_path = os.path.join(
        env['resultdir'], 'multinode')

    # Yes, if the external network isn't found we take the external ip in the
    # pool used for OpenStack services (like the apis) This mimic what was done
    # before the enoslib integration. An alternative solution would be to
    # provision a external pool of ip regardless the number of nic available
    # (in g5k this would be a kavlan) but in this case we'll need to know
    # whether the network is physicaly attached (or no) to the physical nics
    provider_net = lookup_network(env['networks'],
                                  [NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])
    if not provider_net:
        msg = "External network not found, you must define %s networks" % " or ".join([NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])
        raise Exception(msg)

    playbook_values.update({"provider_net": provider_net})
    run_ansible([playbook_path],
                inventory_path,
                extra_vars=playbook_values)


@enostask()
@check_env
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
    playbook_values = mk_enos_values(env)
    workload_dir = seekpath(kwargs["--workload"])
    with open(os.path.join(workload_dir, "run.yml")) as workload_f:
        workload = yaml.load(workload_f)
        for bench_type, desc in workload.items():
            scenarios = desc.get("scenarios", [])
            reset = kwargs.get("--reset")
            for idx, scenario in enumerate(scenarios):
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
                    inventory_path = os.path.join(
                        env['resultdir'], 'multinode')
                    # NOTE(msimonin) all the scenarios and plugins
                    # must reside on the workload directory
                    scenario_location = os.path.join(
                        workload_dir, scenario["file"])
                    bench = {
                        'type': bench_type,
                        'scenario_location': scenario_location,
                        'file': scenario["file"],
                        'args': a
                    }
                    bench.update({'reset': False})
                    if reset and idx == 0:
                        bench.update({'reset': True})

                    if "plugin" in scenario:
                        plugin = os.path.join(workload_dir,
                                           scenario["plugin"])
                        if os.path.isdir(plugin):
                            plugin = plugin + "/"
                        bench['plugin_location'] = plugin
                    playbook_values.update(bench=bench)

                    run_ansible([playbook_path],
                                inventory_path,
                                extra_vars=playbook_values)


@enostask()
@check_env
def backup(env=None, **kwargs):

    backup_dir = kwargs['--backup_dir'] \
        or kwargs['--env'] \
        or SYMLINK_NAME

    backup_dir = os.path.abspath(backup_dir)
    # create if necessary
    if not os.path.isdir(backup_dir):
        os.mkdir(backup_dir)
    # update the env
    env['config']['backup_dir'] = backup_dir
    playbook_path = os.path.join(ANSIBLE_DIR, 'backup.yml')
    inventory_path = os.path.join(env['resultdir'], 'multinode')
    run_ansible([playbook_path], inventory_path, extra_vars=env['config'])


@enostask()
def new(env=None, **kwargs):
    from utils.constants import TEMPLATE_DIR
    logging.debug('phase[new]: args=%s' % kwargs)
    with open(os.path.join(TEMPLATE_DIR, 'reservation.yaml.sample'),
              mode='r') as content:
        print(content.read())


@enostask()
@check_env
def tc(env=None, **kwargs):
    """
    Usage: enos tc [-e ENV|--env=ENV] [--test] [-s|--silent|-vv]
    Enforce network constraints
    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                        use this option when you want to link a specific
                        experiment.
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    --test               Test the rules by generating various reports.
    -vv                  Verbose mode.
    """

    roles = env["rsc"]
    inventory = env["inventory"]
    test = kwargs['--test']
    if test:
        validate_network(roles, inventory)
    else:
        network_constraints = env["config"]["network_constraints"]
        emulate_network(roles, inventory, network_constraints)


@enostask()
def info(env=None, **kwargs):
    if not kwargs['--out']:
        pprint.pprint(env)
    elif kwargs['--out'] == 'json':
        print(json.dumps(env, default=operator.attrgetter('__dict__')))
    elif kwargs['--out'] == 'pickle':
        print(pickle.dumps(env))
    elif kwargs['--out'] == 'yaml':
        print(yaml.dump(env))
    else:
        print("--out doesn't suppport %s output format" % kwargs['--out'])
        print(info.__doc__)


@enostask()
@check_env
def destroy(env=None, **kwargs):
    hard = kwargs['--hard']
    if hard:
        logging.info('Destroying all the resources')
        provider = make_provider(env)
        provider.destroy(env)
    else:
        command = ['destroy', '--yes-i-really-really-mean-it']
        if kwargs['--include-images']:
            command.append('--include-images')
        kolla_kwargs = {'--': True,
                  '--env': kwargs['--env'],
                  '-v': kwargs['-v'],
                  '<command>': command,
                  '--silent': kwargs['--silent'],
                  'kolla': True}
        _kolla(env=env, **kolla_kwargs)


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


@enostask()
@check_env
def kolla(env=None, **kwargs):
    _kolla(env=env, **kwargs)


def _kolla(env=None, **kwargs):
    logging.info('Kolla command')
    logging.info(kwargs)
    kolla_path = get_and_bootstrap_kolla(env, force=False)
    kolla_cmd = [os.path.join(kolla_path, "tools", "kolla-ansible")]
    kolla_cmd.extend(kwargs['<command>'])
    kolla_cmd.extend(["-i", "%s/multinode" % env['resultdir'],
                      "--passwords", "%s/passwords.yml" % env['resultdir'],
                      "--configdir", "%s" % env['resultdir']])
    logging.info(kolla_cmd)
    in_kolla(kolla_cmd)


def _set_resultdir(name=None):
    """Set or get the directory to store experiment results.

    Looks at the `name` and create the directory if it doesn't exist
    or returns it in other cases. If the name is `None`, then the
    function generates an unique name for the results directory.
    Finally, it links the directory to `SYMLINK_NAME`.

    :param name: file path to an existing directory. It could be
    weather an absolute or a relative to the current working
    directory.

    Returns the file path of the results directory.

    """
    # Compute file path of results directory
    resultdir_name = name or 'enos_' + datetime.today().isoformat()
    resultdir_path = os.path.abspath(resultdir_name)

    # Raise error if a related file exists
    if os.path.isfile(resultdir_path):
        raise EnosFilePathError(resultdir_path,
                                "Result directory cannot be created due "
                                "to existing file %s" % resultdir_path)

    # Create the result directory if it does not exist
    if not os.path.isdir(resultdir_path):
        os.mkdir(resultdir_path)
        logging.info('Generate results directory %s' % resultdir_path)

    # Symlink the result directory with the 'cwd/current' directory
    link_path = SYMLINK_NAME
    if os.path.lexists(link_path):
        os.remove(link_path)
    try:
        os.symlink(resultdir_path, link_path)
        logging.info("Symlink %s to %s" % (resultdir_path, link_path))
    except OSError:
        # An harmless error can occur due to a race condition when
        # multiple regions are simultaneously deployed
        logging.warning("Symlink %s to %s failed" %
                        (resultdir_path, link_path))

    return resultdir_path
