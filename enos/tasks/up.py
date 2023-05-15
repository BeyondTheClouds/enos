# -*- coding: utf-8 -*-
"""
Get resources on the testbed and install dependencies.
"""

import logging
import os
from pathlib import Path
from operator import methodcaller

import enoslib as elib
import enoslib.api as elib_api
from enoslib.enos_inventory import EnosInventory

from enos.services import KollaAnsible
import enos.utils.constants as C
from enos.utils.extra import (generate_inventory, get_vip_pool,
                              make_provider, ip_generator, seekpath)

from typing import Optional, Dict, Any

LOGGER = logging.getLogger(__name__)


def up(env: elib.Environment,
       config: Dict[str, Any],
       is_force_deploy: bool,
       is_pull_only: bool,
       tags: Optional[str]):
    """Get resources on the testbed and install dependencies.

    Args:
        config: A dict with information such as the provider, resources, etc,
          as provided by the configuration file (reservation.yaml).
        is_force_deploy: If true, start from a fresh environment.
        is_pull_only: Only pull dependencies. Do not install them.
        tags: Only run ansible tasks tagged with these values.
        env: State for the current experiment

    Put into the env:
        config: Configuration (as a dict)
        inventory: Path to the inventory file
        rsc/networks: Enoslib rscs and networks
        docker: The Docker service
        kolla-ansible: The kolla-ansible service

    Raises:
        EnosUnknownProvider: if the provider name in the configuration file
          does not match to a known provider.

    """

    # Get the provider and update config with provider default values
    provider_type = config['provider']['type']
    provider = make_provider(provider_type)
    provider_conf = dict(provider.default_config(), **config['provider'])
    config.update(provider=provider_conf)
    LOGGER.debug(f"Loaded config {config}")
    env['config'] = config

    # Call the provider to initialize resources
    rsc, networks = provider.init(config, is_force_deploy)
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
    rsc = elib.sync_info(rsc, networks)
    LOGGER.debug(f"Provider resources: {rsc}")
    LOGGER.debug(f"Provider network information: {networks}")

    # Configure node-specific variables such as "network_interface".
    # Enoslib will then include these variables in the inventory so that
    # Kolla will be able to use them.
    for host in rsc.all():
        for network_name in [C.NETWORK_INTERFACE, C.API_INTERFACE,
                             C.NEUTRON_EXTERNAL_INTERFACE]:
            if networks[network_name]:
                physical_interfaces = host.filter_interfaces(networks[network_name]) # noqa
                if physical_interfaces:
                    host.set_extra(**{network_name: physical_interfaces[0]})

    # Generates inventory for ansible/kolla
    inventory = os.path.join(str(env.env_name), 'multinode')
    inventory_conf = env['config'].get('inventory')
    if not inventory_conf:
        LOGGER.debug("No inventory specified, using the sample.")
        base_inventory = os.path.join(C.RSCS_DIR, 'inventory.sample')
    else:
        base_inventory = seekpath(inventory_conf)
    generate_inventory(rsc, networks, base_inventory, inventory)
    LOGGER.info('Generates inventory %s' % inventory)
    env['inventory'] = inventory

    # Ensures rsc contains all groups defined by the inventory (e.g.,
    # 'enos/registry', 'enos/influx', 'haproxy', ...).
    #
    rsc = build_rsc_with_inventory(rsc, env['inventory'])
    env['rsc'] = rsc
    env['networks'] = networks

    # Get variables required by the application
    vip_pool = get_vip_pool(networks)
    ips = ip_generator(vip_pool)
    env['config'].update({
        'vip':               next(ips),
        'influx_vip':        next(ips),
        'grafana_vip':       next(ips),
        'resultdir':         str(env.env_name),
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
    else:
        error_msg = (f"Docker registry mirror of type \"{docker_type}\" "
                     "is not supported")
        raise Exception(error_msg)

    LOGGER.info(f'Deploying docker service as {docker.registry_opts}')
    docker.deploy()
    env['docker'] = docker

    # Install kolla-ansible and run bootstrap-servers
    kolla_globals_values = {
        'kolla_internal_vip_address': env['config']['vip'],
        'influx_vip': env['config']['influx_vip'],
        'resultdir': str(env.env_name),
        'docker_custom_config': mk_kolla_docker_custom_config(docker),
        'docker_disable_default_iptables_rules': False,
        'docker_disable_default_network': False,
        'cwd': os.getcwd()
    }
    kolla_globals_values.update(env['config'].get('kolla', {}))
    kolla_ansible = KollaAnsible(
        config_dir=env.env_name,
        inventory_path=inventory,
        pip_package=env['config'].get('kolla-ansible'),
        globals_values=kolla_globals_values)

    # Do not rely on kolla-ansible for docker, we already managed it with
    # enoslib previously.
    # https://github.com/openstack/kolla-ansible/blob/stable/ussuri/ansible/roles/baremetal/defaults/main.yml
    # https://docs.openstack.org/kolla-ansible/ussuri/reference/deployment-and-bootstrapping/bootstrap-servers.html
    kolla_ansible.execute([
        'bootstrap-servers',
        '--extra enable_docker_repo=false',
        ('--verbose' if logging.root.level <= logging.DEBUG else '')
    ])
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
                      gather_facts=True,
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
        # requests/urllib3 bug: https://github.com/docker/docker-py/issues/3113
        yml.pip(
            **title('Install the bare necessities (pip)'),
            name=['docker', 'requests==2.28.2', 'urllib3<2', 'influxdb'],
            executable='pip3')

        # nscd prevents kolla-toolbox to start. See,
        # https://bugs.launchpad.net/kolla-ansible/+bug/1680139
        yml.systemd(
            **title('Stop nscd to prevent kolla-toolbox error'),
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


# Utils

def title(title: str) -> Dict[str, str]:
    "A title for an ansible yaml commands"

    return {"task_name": "enos up : " + title}


def mk_kolla_docker_custom_config(docker: elib.Docker) -> Dict[str, Any]:
    '''Docker daemon conf for kolla-ansible that reflects elib.Docker

    Kolla-ansible overwrites the Docker daemon configuration that is setup by
    enoslib.  This function makes a specific Docker custom config for
    kolla-ansible that reflects enoslib setup.

    See https://github.com/BeyondTheClouds/enos/issues/345

    '''
    docker_custom_config: Dict[str, Any] = {'debug': True}

    if 'ip' in docker.registry_opts:
        ip = docker.registry_opts["ip"]
        port = docker.registry_opts["port"]
        mirror = f"http://{ip}:{port}"

        docker_custom_config.update({
            'registry-mirrors': [mirror],
            'insecure-registries': [mirror],
        })

    return docker_custom_config


def build_rsc_with_inventory(
        rsc: elib.Roles, inventory_path: str) -> elib.Roles:
    '''Return a new `rsc` with roles from the inventory.

    In enos, we have a strong binding between enoslib roles and kolla-ansible
    groups.  We need for instance to know hosts of the 'enos/registry' group.
    This method takes an enoslib Roles object and an inventory_path and returns
    a new Roles object that contains all groups (as in the inventory file) with
    their hosts (as in enoslib).

    '''

    inv = EnosInventory(sources=inventory_path)
    rsc_by_name = {h.alias: h for h in elib_api.get_hosts(rsc, 'all')}

    # Build a new rsc with all groups in it
    new_rsc = rsc.copy()
    for grp in inv.list_groups():
        hostnames_in_grp = map(methodcaller('get_name'), inv.get_hosts(grp))
        rsc_in_grp = [rsc_by_name[h_name] for h_name in hostnames_in_grp
                      if h_name in rsc_by_name]
        new_rsc.update({grp: rsc_in_grp})

    return new_rsc
