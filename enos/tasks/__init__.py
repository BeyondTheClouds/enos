# -*- coding: utf-8 -*-
import itertools
import logging
import os
from pathlib import Path

import enoslib as elib
from enoslib.task import get_or_create_env
import yaml
from enos.services import RallyOpenStack, Shaker
from enos.utils.build import create_configuration
from enos.utils.constants import (ANSIBLE_DIR, NETWORK_INTERFACE,
                                  NEUTRON_EXTERNAL_INTERFACE)
from enos.utils.extra import (lookup_network, make_provider, setdefault_lazy,
                              eget)

from typing import List, Optional, Dict, Any

# Huge tasks are split in separate files
from enos.tasks.new import new
from enos.tasks.up import up


__all__ = ['new', 'up', 'kolla_ansible', 'install_os',
           'init_os', 'bench', 'backup', 'tc', 'destroy_infra',
           'destroy_os', 'build']


def kolla_ansible(env: elib.Environment, kolla_cmd: List[str]):
    """Call kolla-ansible

    Args:
        env: State for the current experiment
        kolla_cmd: kolla-ansible command and arguments

    Read from the env:
        kolla-ansible: The kolla-ansible service.
    """

    if logging.root.level <= logging.DEBUG:
        kolla_cmd.append('--verbose')

    logging.info(f"Calling Kolla with args {kolla_cmd} ...")
    eget(env, 'kolla-ansible').execute(kolla_cmd)


def install_os(env: elib.Environment,
               is_reconfigure: bool,
               is_pull_only: bool,
               tags: Optional[str]):
    """Install OpenStack with kolla-ansible

    Args:
        env: State for the current experiment.
        is_reconfigure: Only reconfigure the services (after a first
           deployment).
        is_pull_only: Only pull dependencies. Do not install them.
        tags: Only run ansible tasks tagged with these values.

    Read from the env:
        kolla-ansible: The kolla-ansible service
    """

    kolla_cmd = []

    if is_reconfigure:
        kolla_cmd.append('reconfigure')
    elif is_pull_only:
        kolla_cmd.append('pull')
    else:
        kolla_cmd.append('deploy')

    if tags:
        kolla_cmd.append(f'--tags "\'{tags}\'"')

    kolla_ansible(env, kolla_cmd)


def init_os(env: elib.Environment, is_pull_only: bool):
    """Initialize OpenStack with the bare necessities

    Args:
        env: State for the current experiment
        is_pull_only: Only pull dependencies. Do not install them.

    Read from the env:
        inventory: Path to the inventory file
        networks: Enoslib networks
        kolla-ansible: The kolla-ansible service
    """
    playbook_path = os.path.join(ANSIBLE_DIR, 'init_os.yml')
    inventory_path = eget(env, 'inventory')

    # Yes, if the external network isn't found we take the external ip in the
    # pool used for OpenStack services (like the apis) This mimic what was done
    # before the enoslib integration. An alternative solution would be to
    # provision a external pool of ip regardless the number of nic available
    # (in g5k this would be a kavlan) but in this case we'll need to know
    # whether the network is physicaly attached (or no) to the physical nics
    provider_net = lookup_network(
        eget(env, 'networks'),
        [NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])

    if not provider_net:
        msg = "External network not found, define %s networks" % " or ".join(
            [NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE])
        raise Exception(msg)

    options = {
        'provider_net': provider_net,
        'os_env': eget(env, 'kolla-ansible').get_admin_openrc_env_values(),
        'enos_action': 'pull' if is_pull_only else 'deploy'
    }
    elib.run_ansible([playbook_path], inventory_path, extra_vars=options)


def bench(env: elib.Environment,
          workload_dir: Path,
          is_reset: bool,
          is_pull_only: bool):
    """Run benchmark on OpenStack

    Args:
        env: State for the current experiment.
        workload_dir: Path to the workload directory.
        is_pull_only: Only pull dependencies. Do not install them.
        is_reset: Recreate the benchmark environment.

    Put into the env:
        rally: The RallyOpenStack service if any
        shaker: The Shaker service if any

    Read from the env:
        rsc: Enoslib resources
        kolla-ansible: The kolla-ansible service
    """
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

    if is_pull_only:
        RallyOpenStack.pull(agents=eget(env, 'rsc')['enos/bench'])
        Shaker.pull(agents=eget(env, 'rsc')['enos/bench'])
        return

    # Get rally service
    rally = setdefault_lazy(
        env, 'rally',
        lambda: RallyOpenStack(agents=eget(env, 'rsc')['enos/bench']))

    # Get shaker service
    shaker = setdefault_lazy(
        env, 'shaker',
        lambda: Shaker(agents=eget(env, 'rsc')['enos/bench']))

    with open(workload_dir / "run.yml") as workload_f:
        workload = yaml.safe_load(workload_f)

        # Deploy rally if need be
        if 'rally' in workload and workload['rally'].get('enabled', False):
            rally.deploy(
                eget(env, 'kolla-ansible').get_admin_openrc_env_values(),
                is_reset)

        # Deploy shaker if need be
        if 'shaker' in workload and workload['rally'].get('enabled', False):
            shaker.deploy(
                eget(env, 'kolla-ansible').get_admin_openrc_env_values(),
                is_reset)

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


def backup(env: elib.Environment, backup_dir: Path):
    """Backups OpenStack logs and rally, shaker, ... if exist

    Args:
        env: State for the current experiment.
        backup_dir: Path to the backup directory.

    Put into the env:
        backup_dir: Path to the backup directory.

    Read from the env:
        config: Configuration (as a dict)

        # If available
        kolla-ansible: The kolla-ansible service
        rally: The RallyOpenStack service
        shaker: The Shaker service
        docker: The Docker service
    """
    # Create the backup directory if any
    if not backup_dir.is_dir():
        backup_dir.mkdir()

    # Backups services
    if 'kolla-ansible' in env:
        eget(env, 'kolla-ansible').backup(backup_dir)

    if 'rally' in env:
        eget(env, 'rally').backup(backup_dir)

    if 'shaker' in env:
        eget(env, 'shaker').backup(backup_dir)

    if 'docker' in env:
        eget(env, 'docker').backup()

    # Backup enos monitoring
    eget(env, 'config').update(backup_dir=str(backup_dir))
    options = {}
    options.update(eget(env, 'config'))
    options.update({'enos_action': 'backup'})
    playbook_path = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = eget(env, 'inventory')
    elib.run_ansible([playbook_path], inventory_path, extra_vars=options)


def tc(env: elib.Environment,
       validate: bool,
       is_reset: bool,
       network_constraints: Dict[str, str] = None,
       extra_vars: Dict[str, Any] = {}):
    """Applies network constraints

    Args:
        env: State for the current experiment.
        validate: If true, test rule enforcement. (Get them back with `backup`).
        is_reset: If true, reset the constraints.
        network_constraints: See enoslib API.
        extra_vars: Extra variables for the application of constraints.

    Read from the env:
        rsc: Enoslib resources
        config: Configuration (as a dict)

    """

    rsc = eget(env, "rsc")

    # We inject the influx_vip for annotation purpose
    extra_vars.update(influx_vip=eget(env, 'config').get('influx_vip'))

    if not network_constraints:
        # Find the network_constraints from the config file
        network_constraints = eget(env, 'config').get("network_constraints", {})

    netem = elib.Netem(network_constraints, roles=rsc, extra_vars=extra_vars)
    if is_reset:
        netem.destroy()
    else:
        netem.deploy()

    if validate:
        netem.validate()


def destroy_infra(env: elib.Environment):
    """Destroy resources acquired on the testbed

    Args:
        env: State for the current experiment.

    Read from the env:
        config: Configuration (as a dict)

    """

    provider_conf = eget(env, 'config')['provider']
    provider = make_provider(provider_conf)

    logging.info(f'Destroying resources acquired on {provider}...')
    provider.destroy(env)


def destroy_os(env: elib.Environment, include_images: bool):
    """Destroy OpenStack from the testbed

    Destroy includes (if any): Monitoring stack, Rally, Shaker.

    Args:
        env: State for the current experiment.
        include_images: Also remove OpenStack images from Docker.

    Read from the env:
        inventory: The inventory path
        kolla-ansible: The kolla-ansible service

        # If available
        rally: The RallyOpenStack service
        shaker: The Shaker service

    """

    # Destroy OpenStack
    eget(env, 'kolla-ansible').destroy(
        include_images,
        logging.root.level <= logging.DEBUG)

    if 'rally' in env:
        eget(env, 'rally').destroy()

    if 'shaker' in env:
        eget(env, 'shaker').destroy()

    # Destroy enos monitoring
    options = {
        "enos_action": "destroy"
    }
    up_playbook = os.path.join(ANSIBLE_DIR, 'enos.yml')
    inventory_path = eget(env, 'inventory')
    elib.run_ansible([up_playbook], inventory_path, extra_vars=options)


def build(provider: str, config_options: Dict[str, Any]):
    """Build a reference image for later deployment

    It is up to the user to then save the image (e.g., vagrant box, kaenv ...).

    Args:
        provider
        config_options: A dict with information such as image, or box.
        env: State for the current experiment

    """
    config = create_configuration(provider, **config_options)
    is_force_deploy = True
    is_pull_only = True
    env = get_or_create_env(True, None)

    # Deploy in pull_only mode
    up(env, config, is_force_deploy, is_pull_only, None)
    install_os(env, False, is_pull_only, None)
    init_os(env, is_pull_only)
