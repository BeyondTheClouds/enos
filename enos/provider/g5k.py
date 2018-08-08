# -*- coding: utf-8 -*-
import logging

import execo as EX

import enoslib.infra.enos_g5k.api as enoslib_gapi
import enoslib.infra.enos_g5k.provider as enoslib_g5k
from enoslib.api import expand_groups

from enos.provider.provider import Provider
from enos.utils.extra import gen_enoslib_roles


DEFAULT_CONN_PARAMS = {'user': 'root'}


logger = logging.getLogger(__name__)


PRIMARY_NETWORK = {
    "id": "int-net",
    "site": "rennes",
    "type": "kavlan",
    "role": "network_interface"}


SECONDARY_NETWORK = {
    "id": "ext-net",
    "site": "rennes",
    "type": "kavlan",
    "role": "neutron_network_interface"}


def _count_common_interfaces(clusters):
    interfaces = enoslib_gapi.get_clusters_interfaces(clusters)
    return min([len(x) for x in interfaces.values()])


def _build_enoslib_conf(conf):
    enoslib_conf = conf.get("provider", {})
    if enoslib_conf.get("resources") is not None:

        # enoslib mode
        logger.debug("Getting resources specific to the provider")
        return enoslib_conf

    # EnOS legacy mode
    logger.debug("Getting generic resources from configuration")
    machines = []
    networks = [PRIMARY_NETWORK]
    clusters = set()

    # get a plain configuration of resources
    resources = conf.get("resources", {})

    # when an advanced configuration is present (aka topology)
    # replace resources with that configuration
    resources = conf.get("topology", resources)
    for desc in gen_enoslib_roles(resources):
        groups = expand_groups(desc["group"])
        for group in groups:
            clusters.add(desc["flavor"])
            machine = {"roles": [group, desc["role"]],
                       "nodes": desc["number"],
                       "cluster": desc["flavor"],
                       "primary_network": "int-net",
                       "secondary_networks": []}
            machines.append(machine)

    # check minimum available number of interfaces in each cluster
    network_count = _count_common_interfaces(clusters)
    if network_count > 1:
        networks.append(SECONDARY_NETWORK)

        # add a secondary network
        for machine in machines:
            machine["secondary_networks"] = ["ext-net"]

    enoslib_conf.update({"resources":
                         {"machines": machines,
                          "networks": networks}})

    return enoslib_conf


def _exec_command_on_nodes(nodes, cmd, label, conn_params=None):
    """Execute a command on a node (id or hostname) or on a set of nodes"""
    if isinstance(nodes, basestring):
        nodes = [nodes]

    if conn_params is None:
        conn_params = DEFAULT_CONN_PARAMS

    logger.info(label)
    remote = EX.Remote(cmd, nodes, conn_params)
    remote.run()

    if not remote.finished_ok:
        raise Exception('An error occcured during remote execution')


def _provision(roles):
    nodes = []
    for value in roles.values():
        nodes.extend(value)

    # remove duplicate hosts
    # Note(jrbalderrama): do we have to implement hash/equals in Host?
    nodes = set([node.address for node in nodes])

    # Provision nodes so we can run Ansible on it
    _exec_command_on_nodes(
        nodes,
        'apt-get update && apt-get -y --force-yes install python',
        'Installing python...')

    # Bind volumes of docker in /tmp (free storage location on G5k)
    _exec_command_on_nodes(
        nodes,
        ('mkdir -p /tmp/docker/volumes; '
         'mkdir -p /var/lib/docker/volumes'),
        'Creating docker volumes directory in /tmp')

    _exec_command_on_nodes(
        nodes,
        ('(mount | grep /tmp/docker/volumes) || '
         'mount --bind /tmp/docker/volumes /var/lib/docker/volumes'),
        'Bind mount')

    # Bind nova local storage in /tmp
    _exec_command_on_nodes(
        nodes,
        'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
        'Creating nova directory in /tmp')
    _exec_command_on_nodes(
        nodes,
        '(mount | grep /tmp/nova) || ',
        'mount --bind /tmp/nova /var/lib/nova',
        'Bind mount')


class G5k(Provider):
    """Grid'5000 provider implementation.
    """

    def init(self, config, force=False):
        logger.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(config)
        logger.debug("Creating G5K provider")
        g5k = enoslib_g5k.G5k(enoslib_conf)
        logger.info("Initializing G5K provider")
        roles, networks = g5k.init(force)
        _provision(roles)
        return roles, networks

    def destroy(self, env):
        conf = env.get('config')
        logger.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(conf)
        logger.debug("Creating G5K provider")
        g5k = enoslib_g5k.G5k(enoslib_conf)
        logger.info("Destroying G5K deployment")
        g5k.destroy()

    def default_config(self):
        return {'job_name': 'Enos',
                'walltime': '02:00:00',
                'env_name': 'debian9-x64-min',
                'reservation': False,
                'user': 'root'}

    def __str__(self):
        return 'G5k'
