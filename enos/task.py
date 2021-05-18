# -*- coding: utf-8 -*-
import itertools
import json
import logging
import os
import pathlib
import pickle
from typing import Dict

import enoslib as elib
import yaml
from enos.services import RallyOpenStack, Shaker
# from enos.utils.build import create_configuration
from enos.utils.constants import (ANSIBLE_DIR, NETWORK_INTERFACE,
    NEUTRON_EXTERNAL_INTERFACE, SYMLINK_NAME)
from enos.utils.extra import (lookup_network, make_provider, seekpath,
                              setdefault_lazy, check_env)


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
            for _, scenario in enumerate(scenarios):
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
        print(json.dumps(env.data, default=json_encoder, indent=True))
    elif kwargs['--out'] == 'pickle':
        print(pickle.dumps(env.data))
    elif kwargs['--out'] == 'yaml':
        print(yaml.dump(env.data))
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


def build(provider, **kwargs):
    # # XXX: configuration. make a temporary configuration file and give it to
    # # deploy as `configuration_file`.
    # configuration = create_configuration(provider, **kwargs)
    # arguments = {
    #     '--force-deploy': True,
    #     '--pull': True,
    #     '--env': None
    # }
    #
    # deploy(configuration, **arguments)
    pass


def title(title: str) -> Dict[str, str]:
    "A title for an ansible yaml commands"
    return {"display_name": "Enos : " + title}
