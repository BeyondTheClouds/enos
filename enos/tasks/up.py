# -*- coding: utf-8 -*-
"""
Get resources on the testbed and install dependencies.
"""

import logging
import os
from pathlib import Path

import enoslib as elib
import yaml

from enos.utils.errors import EnosFilePathError
from enos.services import KollaAnsible
import enos.utils.constants as C
from enos.utils.extra import (build_rsc_with_inventory, generate_inventory,
                              get_vip_pool, make_provider, pop_ip, seekpath)

from typing import List, Optional, Dict, Any

LOGGER = logging.getLogger(__name__)


def load_config(config_file: Path) -> Dict[str, Any]:
    "Load the configuration yaml file"

    # Ensure `config_file` points to a file
    if not config_file.is_file():
        raise EnosFilePathError(
            config_file,
            f'Configuration file {config_file} does not exist')

    # Parse it
    with open(config_file, 'r') as yaml_file:
        config = yaml.safe_load(yaml_file)
        LOGGER.info(f"Loaded configuration file {config_file}")
        return config


@elib.enostask(new=True)
def up(config_file: Path,
       is_force_deploy: bool,
       is_pull_only: bool,
       tags: Optional[List[str]],
       env: elib.Environment = None):
    """
    Get resources on the testbed and install dependencies.

    Put into the env:
    - config_file: Path to the configuration file
    - config: Configuration (dict)
    - inventory: Path to the inventory file
    - rsc/networks: Enoslib rscs and networks
    - docker: The docker service
    - kolla-ansible: The kolla-ansible service
    """

    # Load the configuration
    config = load_config(config_file)
    env['config_file'] = config_file

    # Get the provider and update config with provider default values
    provider_type = config['provider']['type']
    provider = make_provider(provider_type)
    provider_conf = dict(provider.default_config(), **config['provider'])
    config.update(provider=provider_conf)
    env['config'] = config
    LOGGER.debug("Loaded config: %s", config)

    # Call the provider to initialize resources
    rsc, networks = provider.init(env['config'], is_force_deploy)
    LOGGER.debug(f"Provider resources: {rsc}")
    LOGGER.debug(f"Provider network information: {networks}")

    # Generates inventory for ansible/kolla
    inventory = os.path.join(str(env['resultdir']), 'multinode')
    inventory_conf = env['config'].get('inventory')
    if not inventory_conf:
        LOGGER.debug("No inventory specified, using the sample.")
        base_inventory = os.path.join(C.RSCS_DIR, 'inventory.sample')
    else:
        base_inventory = seekpath(inventory_conf)
    generate_inventory(rsc, networks, base_inventory, inventory)
    LOGGER.info('Generates inventory %s' % inventory)

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
        'cwd':               str(Path.cwd()),
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

    LOGGER.info(f'Deploying docker service as {docker.registry_opts}')
    docker.deploy()

    env['docker'] = docker

    # Install kolla-ansible and run bootstrap-servers
    kolla_globals_values = {
        'kolla_internal_vip_address': env['config']['vip'],
        'influx_vip': env['config']['influx_vip'],
        'resultdir': str(env['resultdir']),
        'cwd':  os.getcwd()
    }
    kolla_globals_values.update(env['config'].get('kolla', {}))
    kolla_ansible = KollaAnsible(
        config_dir=env['resultdir'],
        inventory_path=inventory,
        pip_package=env['config'].get('kolla-ansible'),
        globals_values=kolla_globals_values)

    # Do not rely on kolla-ansible for docker, we already managed it with
    # enoslib previously.
    # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/ansible/roles/baremetal/defaults/main.yml
    # https://docs.openstack.org/kolla-ansible/ussuri/reference/deployment-and-bootstrapping/bootstrap-servers.html
    #
    # TODO: give it tags if any
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

    LOGGER.debug(f"{admin_openrc_path} generated with {os_auth_rc}")

    # Set up machines with bare dependencies
    with elib.play_on(inventory_path=inventory, pattern_hosts='baremetal',
                      extra_vars=kolla_ansible.globals_values) as yml:
        # Remove IP on the external interface if any
        yml.shell(
            "ip addr flush {{ neutron_external_interface }}",
            **title('Remove IP on the external interface (if any)'),
            when="neutron_external_interface is defined")

        # sudo required by `kolla-ansible destroy`.  See
        # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/tools/validate-docker-execute.sh#L7
        yml.apt(
            **title('Install the bare necessities (apt)'),
            name=['sudo', 'git', 'qemu-kvm'],
            update_cache=True)
        yml.pip(
            **title('Install the bare necessities (pip)'),
            name=['docker', 'influxdb'],
            executable='pip3')

        # nscd prevents kolla-toolbox to start. See,
        # https://bugs.launchpad.net/kolla-ansible/+bug/1680139
        yml.systemd(
            **title('Install the bare necessities (pip)'),
            name='nscd', state='stopped', ignore_errors=True)

        # Break RabbitMQ, which expects the hostname to resolve to the
        # API network address.  Remove the troublesome entry.  See
        # https://bugs.launchpad.net/kolla-ansible/+bug/1837699 and
        # https://bugs.launchpad.net/kolla-ansible/+bug/1862739
        for banned_ip in ['127.0.1.1', '127.0.2.1']:
            yml.lineinfile(
                **title(f'Ensure hostname does not point to {banned_ip}'),
                dest='/etc/hosts',
                regexp='^' + banned_ip + '\\b.*\\s{{ ansible_hostname }}\\b.*',
                state='absent')

        # Provider specific provisioning
        if str(provider) == 'Vagrant':
            yml.sysctl(
                **title("RabbitMQ/epmd won't start without IPv6 enabled"),
                name='net.ipv6.conf.all.disable_ipv6',
                value=0,
                state='present')

    # Runs playbook that install monitoring tools (eg, Influx, Monitoring,
    # Grafana)
    options = env['config'].copy()
    options.update(enos_action="pull" if is_pull_only else "deploy")
    up_playbook = os.path.join(C.ANSIBLE_DIR, 'enos.yml')
    elib.run_ansible(
        [up_playbook], env['inventory'], extra_vars=options, tags=tags)


def title(title: str) -> Dict[str, str]:
    "A title for an ansible yaml commands"
    return {"display_name": "enos up : " + title}
