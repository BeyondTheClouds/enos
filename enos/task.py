# -*- coding: utf-8 -*-
import pathlib
import itertools
import json
import logging
import os
import pickle
import yaml
import enoslib as elib

from enos.utils.constants import (SYMLINK_NAME, ANSIBLE_DIR, RSCS_DIR,
                                  NEUTRON_EXTERNAL_INTERFACE,
                                  NETWORK_INTERFACE, TEMPLATE_DIR)
from enos.utils.build import create_configuration
from enos.utils.enostask import check_env
from enos.services import (KollaAnsible, RallyOpenStack, Shaker)
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

    logging.debug(f"Provider resources: {rsc}")
    logging.debug(f"Provider network information: {networks}")

    # Generates inventory for ansible/kolla
    inventory = os.path.join(str(env['resultdir']), 'multinode')
    inventory_conf = env['config'].get('inventory')
    if not inventory_conf:
        logging.debug("No inventory specified, using the sample.")
        base_inventory = os.path.join(RSCS_DIR, 'inventory.sample')
    else:
        base_inventory = seekpath(inventory_conf)
    generate_inventory(rsc, networks, base_inventory, inventory)
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
    # > ansible_ssh_private_key_file='/home/rfish/prog/enos/.vagrant/machines/enos-0/libvirt/private_key' # noqa
    # > ansible_ssh_user='root' enos_devices="['eth1','eth2']"
    # > network_interface='eth1' network_interface_dev='eth1'
    # > network_interface_ip='192.168.42.245'
    # > neutron_external_interface='eth2'
    # > neutron_external_interface_dev='eth2'
    # > neutron_external_interface_ip='192.168.43.245'
    rsc = elib.discover_networks(rsc, networks)
    rsc = build_rsc_with_inventory(rsc, env['inventory'])

    env['rsc'] = rsc
    env['networks'] = networks

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

    # Ensure python3 is on remote targets (kolla requirement)
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
        config_dir=env['resultdir'],
        inventory_path=inventory,
        globals_values=env['config']['kolla'])

    # Do not rely on kolla-ansible for docker, we already managed it with
    # enoslib previously.
    # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/ansible/roles/baremetal/defaults/main.yml
    # https://docs.openstack.org/kolla-ansible/ussuri/reference/deployment-and-bootstrapping/bootstrap-servers.html
    kolla_ansible.execute(['bootstrap-servers',
                           '--extra enable_docker_repo=false'])

    env['kolla-ansible'] = kolla_ansible

    # Generates the admin-openrc, see
    # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/ansible/roles/common/templates/admin-openrc.sh.j2
    admin_openrc_path = env['resultdir'] / 'admin-openrc'
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
        yml.apt(name=['sudo', 'git', 'qemu-kvm'], update_cache=True)
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

    # Runs playbook that install monitoring tools (eg, Influx, Monitoring,
    # Grafana)
    options = env['config'].copy()
    options.update(enos_action="pull" if kwargs.get("--pull") else "deploy")
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
    inventory_path = env['inventory']

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
    logging.debug('phase[bench]: args=%s' % kwargs)

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

    if kwargs.get("--pull"):
        RallyOpenStack.pull(agents=env['rsc']['enos/bench'])
        Shaker.pull(agents=env['rsc']['enos/bench'])
        return

    # Get rally service
    rally = setdefault_lazy(
        env, 'rally', lambda:
        RallyOpenStack(agents=env['rsc']['enos/bench']))

    # Get shaker service
    shaker = setdefault_lazy(
        env, 'shaker', lambda:
        Shaker(agents=env['rsc']['enos/bench']))

    workload_dir = pathlib.Path(seekpath(kwargs["--workload"]))
    with open(workload_dir / "run.yml") as workload_f:
        workload = yaml.safe_load(workload_f)

        # Deploy rally if need be
        if 'rally' in workload.keys():
            rally.deploy(
                env['kolla-ansible'].get_admin_openrc_env_values(),
                kwargs.get("--reset"))

        # Deploy shaker if need be
        if 'shaker' in workload.keys():
            shaker.deploy(
                env['kolla-ansible'].get_admin_openrc_env_values(),
                kwargs.get("--reset"))

        # Parse bench and execute them
        for bench_type, desc in workload.items():
            scenarios = desc.get("scenarios", [])
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
                for args in cartesian(top_args):
                    # Run Rally scenario
                    if bench_type == 'rally':
                        # NOTE(msimonin) Scenarios and plugins
                        # must reside on the workload directory
                        scenario_path = workload_dir / scenario["file"]
                        plugin = (workload_dir / scenario["plugin"]).resolve()\
                            if "plugin" in scenario else None
                        rally.run_scenario(scenario_path, args, plugin)

                    # Run shaker scenario
                    elif bench_type == 'shaker':
                        # Note(rcherrueau): Scenarios path should be local to
                        # the container
                        shaker.run_scenario(scenario['file'])


@elib.enostask()
@check_env
def backup(env=None, **kwargs):
    # Get/create the backup directory
    backup_dir = pathlib.Path(
        kwargs['--backup_dir']
        or kwargs['--env']
        or SYMLINK_NAME).resolve()

    if not backup_dir.is_dir():
        backup_dir.mkdir()

    # Backups services
    if 'kolla-ansible' in env:
        env['kolla-ansible'].backup(backup_dir)

    if 'rally' in env:
        env['rally'].backup(backup_dir)

    if 'shaker' in env:
        env['shaker'].backup(backup_dir)

    if 'docker' in env:
        env['docker'].backup()

    # Backup enos monitoring
    env['config']['backup_dir'] = str(backup_dir)
    options = {}
    options.update(env['config'])
    options.update({'enos_action': 'backup'})
    playbook_path = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = env['inventory']
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
    def json_encoder(o):
        'Render path with str'
        if isinstance(o, pathlib.Path):
            return str(o.resolve())
        else:
            return o.__dict__

    if not kwargs['--out'] or kwargs['--out'] == 'json':
        print(json.dumps(env, default=json_encoder, indent=True))
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

    # Destroy OpenStack (kolla-ansible destroy)
    if 'kolla-ansible' in env:
        env['kolla-ansible'].destroy(
            kwargs.get('--include-images', False),
            kwargs.get('--verbose', False))

    if 'rally' in env:
        env['rally'].destroy()

    if 'shaker' in env:
        env['shaker'].destroy()

    # Destroy enos monitoring
    options = {
        "enos_action": "destroy"
    }
    up_playbook = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = env['inventory']
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
