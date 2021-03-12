# -*- coding: utf-8 -*-
from datetime import datetime
import itertools
import json
import logging
import operator
import os
import pickle
import pprint
import yaml
import enoslib as elib

from enos.utils.constants import (SYMLINK_NAME, ANSIBLE_DIR, RSCS_DIR,
                                  NEUTRON_EXTERNAL_INTERFACE,
                                  NETWORK_INTERFACE, TEMPLATE_DIR)
from enos.utils.kolla import KollaAnsible
from enos.utils.build import create_configuration
from enos.utils.enostask import check_env
from enos.utils.errors import EnosFilePathError
from enos.utils.extra import (generate_inventory, pop_ip, make_provider,
                              load_config, seekpath, get_vip_pool,
                              lookup_network, build_rsc_with_inventory,
                              setdefault_lazy)


@elib.enostask(new=True)
def up(config, config_file=None, env=None, **kwargs):
    logging.debug('phase[up]: args=%s' % kwargs)

    # Get the provider
    provider_conf = config['provider']
    provider = make_provider(provider_conf)

    # Get the configuration
    config = load_config(config, provider.default_config())
    env['config'] = config
    env['config_file'] = config_file
    logging.debug("Loaded config: %s", config)

    # Call the provider and initialize resources
    rsc, networks = \
        provider.init(env['config'], kwargs['--force-deploy'])

    env['rsc'] = rsc
    env['networks'] = networks

    logging.debug(f"Provider ressources: {env['rsc']}")
    logging.debug(f"Provider network information: {env['networks']}")

    # Generates inventory for ansible/kolla
    inventory = os.path.join(str(env['resultdir']), 'multinode')
    inventory_conf = env['config'].get('inventory')
    if not inventory_conf:
        logging.debug("No inventory specified, using the sample.")
        base_inventory = os.path.join(RSCS_DIR, 'inventory.sample')
    else:
        base_inventory = seekpath(inventory_conf)
    generate_inventory(env['rsc'], env['networks'], base_inventory, inventory)
    logging.info('Generates inventory %s' % inventory)

    env['inventory'] = inventory

    # Fills rsc with information such as network_interface and then
    # ensures rsc contains all groups defined by the inventory (e.g.,
    # 'enos/registry', 'enos/influx', 'haproxy', ...).
    #
    # Note(rcherrueau): I keep track of this extra information for a
    # futur migration to enoslib-v6:
    # > enos-0 ansible_host=192.168.121.128 ansible_port='22'
    # > ansible_ssh_common_args='-o StrictHostKeyChecking=no -o
    # > UserKnownHostsFile=/dev/null'
    # > ansible_ssh_private_key_file='/home/rfish/prog/enos/.vagrant/machines/enos-0/libvirt/private_key'
    # > ansible_ssh_user='root' enos_devices="['eth1','eth2']"
    # > network_interface='eth1' network_interface_dev='eth1'
    # > network_interface_ip='192.168.42.245'
    # > neutron_external_interface='eth2'
    # > neutron_external_interface_dev='eth2'
    # > neutron_external_interface_ip='192.168.43.245'
    rsc = elib.discover_networks(rsc, networks)
    rsc = build_rsc_with_inventory(rsc, env['inventory'])

    # Get variables required by the application
    vip_pool = get_vip_pool(networks)
    env['config'].update({
        'vip':               pop_ip(vip_pool),
        'influx_vip':        pop_ip(vip_pool),
        'grafana_vip':       pop_ip(vip_pool),
        'resultdir':         str(env['resultdir']),
        'rabbitmq_password': "demo",
        'database_password': "demo",
        'cwd':               str(pathlib.Path.cwd()),
    })

    # Ensure python3 is on remote target (kolla requirement)
    elib.ensure_python3(make_default=True, roles=rsc)

    # Install the Docker registry
    docker_type = env['config']['registry'].get('type', "internal")
    docker_port = env['config']['registry'].get('port', 5000)
    docker = None

    if docker_type == 'none':
        docker = elib.Docker(agent=rsc['all'],
                             registry_opts={'type': 'none'})
    elif docker_type == 'external':
        docker = elib.Docker(agent=rsc['all'],
                             registry_opts={
                                 'type': 'external',
                                 'ip': env['config']['registry']['ip'],
                                 'port': docker_port})
    elif docker_type == 'internal':
        docker = elib.Docker(agent=rsc['all'],
                             registry=rsc['enos/registry'],
                             registry_opts={
                                 'type': 'internal',
                                 'port': docker_port})

    logging.info(f'Deploying docker service as {docker.registry_opts}')
    docker.deploy()

    env['docker'] = docker

    # Install kolla-ansible and run bootstrap-servers
    env['config']['kolla'].update({
        'kolla_internal_vip_address': env['config']['vip'],
        'influx_vip': env['config']['influx_vip'],
        'resultdir': str(env['resultdir']),
        'cwd':  os.getcwd()
    })
    kolla_ansible = KollaAnsible(
        pip_package=env['config']['kolla-ansible'],
        inventory_path=inventory,
        config_dir=str(env['resultdir']),
        globals_values=env['config']['kolla'])

    kolla_ansible.execute(['bootstrap-servers'])

    env['kolla-ansible'] = kolla_ansible

    # Generates the admin-openrc, see
    # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/ansible/roles/common/templates/admin-openrc.sh.j2
    admin_openrc_path = os.path.join(str(env['resultdir']), 'admin-openrc')
    os_auth_rc = kolla_ansible.get_admin_openrc_env_values()

    with open(admin_openrc_path, mode='w') as admin_openrc:
        for k, v in os_auth_rc.items():
            admin_openrc.write(f'export {k}="{v}"\n')

    logging.debug(f"{admin_openrc_path} generated with {os_auth_rc}")

    # Set up machines with bare dependencies
    with elib.play_on(inventory_path=inventory, pattern_hosts='baremetal',
                      extra_vars=kolla_ansible.globals_values) as yml:
        # Remove IP on the external interface if any
        yml.shell("ip addr flush {{ neutron_external_interface }}",
                  when="neutron_external_interface is defined")

        # sudo required by `kolla-ansible destroy`.  See
        # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/tools/validate-docker-execute.sh#L7
        yml.apt(name=['sudo', 'git', 'fping', 'qemu-kvm'], update_cache=True)
        yml.pip(name=['docker', 'influxdb'], executable='pip3')

        # nscd prevents kolla-toolbox to start. See,
        # https://bugs.launchpad.net/kolla-ansible/+bug/1680139
        yml.systemd(name='nscd', state='stopped', ignore_errors=True)

        # Break RabbitMQ, which expects the hostname to resolve to the
        # API network address.  Remove the troublesome entry.  See
        # https://bugs.launchpad.net/kolla-ansible/+bug/1837699 and
        # https://bugs.launchpad.net/kolla-ansible/+bug/1862739
        for banned_ip in ['127.0.1.1', '127.0.2.1']:
            yml.lineinfile(
                display_name='Ensure hostname does not point to {banned_ip}',
                dest='/etc/hosts',
                regexp='^' + banned_ip + '\\b.*\\s{{ ansible_hostname }}\\b.*',
                state='absent')

        # Provider specific provisioning
        if str(provider) == 'Vagrant':
            yml.sysctl(
                display_name="RabbitMQ/epmd won't start without IPv6 enabled",
                name='net.ipv6.conf.all.disable_ipv6',
                value=0,
                state='present')

    # Runs playbook that initializes resources (eg,
    # install monitoring tools, Rally ...)
    options = {}
    options.update(env['config'])
    enos_action = "pull" if kwargs.get("--pull") else "deploy"
    options.update(enos_action=enos_action)
    up_playbook = os.path.join(ANSIBLE_DIR, 'enos.yml')
    elib.run_ansible([up_playbook], env['inventory'], extra_vars=options,
                     tags=kwargs['--tags'])


@elib.enostask()
@check_env
def install_os(env=None, **kwargs):
    logging.debug('phase[os]: args=%s' % kwargs)

    kolla_cmd = []
    if kwargs.get('--'):
        kolla_cmd.extend(kwargs.get('<kolla-cmd>', []))
    elif kwargs.get('--reconfigure'):
        kolla_cmd.append('reconfigure')
    elif kwargs.get('--pull'):
        kolla_cmd.append('pull')
    else:
        kolla_cmd.append('deploy')

    if kwargs['--tags']:
        kolla_cmd.extend(['--tags', kwargs['--tags']])

    if kwargs['-v']:
        kolla_cmd.append('--verbose')

    logging.info("Calling Kolla...")
    env['kolla-ansible'].execute(kolla_cmd)


@elib.enostask()
@check_env
def init_os(env=None, **kwargs):
    logging.debug('phase[init]: args=%s' % kwargs)

    playbook_path = os.path.join(ANSIBLE_DIR, 'init_os.yml')
    inventory_path = os.path.join(
        str(env['resultdir']), 'multinode')

    # Yes, if the external network isn't found we take the external ip in the
    # pool used for OpenStack services (like the apis) This mimic what was done
    # before the enoslib integration. An alternative solution would be to
    # provision a external pool of ip regardless the number of nic available
    # (in g5k this would be a kavlan) but in this case we'll need to know
    # whether the network is physicaly attached (or no) to the physical nics
    provider_net = lookup_network(
        env['networks'],
        [NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])

    if not provider_net:
        msg = "External network not found, define %s networks" % " or ".join(
            [NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])
        raise Exception(msg)

    options = {
        'provider_net': provider_net,
        'os_env': env['kolla-ansible'].get_admin_openrc_env_values(),
        'enos_action': 'pull' if kwargs.get('--pull') else 'deploy'
    }
    elib.run_ansible([playbook_path],
                     inventory_path,
                     extra_vars=options)


@elib.enostask()
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
                    playbook_path = os.path.join(ANSIBLE_DIR, 'enos.yml')
                    inventory_path = os.path.join(
                        str(env['resultdir']), 'multinode')
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
                    playbook_values.update(enos_action="bench")

                    elib.run_ansible([playbook_path],
                                     inventory_path,
                                     extra_vars=playbook_values)


@elib.enostask()
@check_env
def backup(env=None, **kwargs):

    backup_dir = kwargs['--backup_dir'] \
        or kwargs['--env'] \
        or SYMLINK_NAME

    backup_dir = os.path.abspath(backup_dir)

    if 'docker' in env:
        env['docker'].backup()

    # create if necessary
    if not os.path.isdir(backup_dir):
        os.mkdir(backup_dir)
    # update the env
    env['config']['backup_dir'] = backup_dir
    options = {}
    options.update(env['config'])
    options.update({'enos_action': 'backup'})
    playbook_path = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = os.path.join(str(env['resultdir']), 'multinode')
    elib.run_ansible([playbook_path], inventory_path, extra_vars=options)


def new(env=None, **kwargs):
    logging.debug('phase[new]: args=%s' % kwargs)
    with open(os.path.join(TEMPLATE_DIR, 'reservation.yaml.sample'),
              mode='r') as content:
        print(content.read())


@elib.enostask()
@check_env
def tc(env=None, network_constraints=None, extra_vars=None, **kwargs):
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
    # We inject the influx_vip for annotation purpose
    influx_vip = env["config"].get("influx_vip")
    test = kwargs['--test']
    reset = kwargs['--reset']
    if not extra_vars:
        extra_vars = {}
    extra_vars.update(influx_vip=influx_vip)

    from enoslib.service import Netem

    if not network_constraints:
        network_constraints = env["config"].get("network_constraints", {})

    netem = Netem(network_constraints, roles=roles, extra_vars=extra_vars)
    if test:
        netem.validate()
    elif reset:
        netem.destroy()
    else:
        netem.deploy()


@elib.enostask()
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


@elib.enostask()
@check_env
def destroy(env=None, **kwargs):
    # Destroy machine/network resources
    if kwargs['--hard']:
        logging.info('Destroying all the resources')
        provider_conf = env['config']['provider']
        provider = make_provider(provider_conf)
        provider.destroy(env)
        return

    # Destroy OpenStack (kolla-ansible destroy) + monitoring + rally
    # Destroying kolla resources
    kolla_cmd = ['destroy', '--yes-i-really-really-mean-it']
    if kwargs['--include-images']:
        kolla_cmd.append('--include-images')
    if kwargs['-v']:
        kolla_cmd.append('--verbose')
    env['kolla-ansible'].execute(kolla_cmd)

    # Destroy enos resources
    options = {
        "enos_action": "destroy"
    }
    up_playbook = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = os.path.join(str(env['resultdir']), 'multinode')
    elib.run_ansible([up_playbook], inventory_path, extra_vars=options)


def deploy(config, config_file=None, **kwargs):
    # --reconfigure and --tags can not be provided in 'deploy'
    # but they are required for 'up' and 'install_os'
    kwargs['--reconfigure'] = False
    kwargs['--tags'] = None

    up(config, config_file=config_file, **kwargs)

    # If the user doesn't specify an experiment, then set the ENV directory to
    # the default one.
    if not kwargs['--env']:
        kwargs['--env'] = SYMLINK_NAME

    install_os(**kwargs)
    init_os(**kwargs)


def build(provider, **kwargs):
    configuration = create_configuration(provider, **kwargs)
    arguments = {
        '--force-deploy': True,
        '--pull': True,
        '--env': None
    }

    deploy(configuration, **arguments)


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
