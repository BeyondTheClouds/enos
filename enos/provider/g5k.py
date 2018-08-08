# -*- coding: utf-8 -*-
import logging

from enoslib.api import expand_groups
from enoslib.infra.enos_g5k import api
from enoslib.infra.enos_g5k import provider

from enos.provider.provider import Provider
from enos.utils.extra import gen_enoslib_roles


LOGGER = logging.getLogger(__name__)

DEFAULT_CONN_PARAMS = {'user': 'root'}

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
    interfaces = api.get_clusters_interfaces(clusters)
    return min([len(x) for x in interfaces.values()])


def _build_enoslib_conf(conf):
    enoslib_conf = conf.get("provider", {})
    if enoslib_conf.get("resources") is not None:

        # enoslib mode
        LOGGER.debug("Getting resources specific to the provider")
        return enoslib_conf

    # EnOS legacy mode
    LOGGER.debug("Getting generic resources from configuration")
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
                       "secondary_networks": [],
                       # ensure at least one node
                       "min": 1}
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


def _provision(roles):
    nodes = []
    for value in roles.values():
        nodes.extend(value)

    # remove duplicate hosts
    # Note(jrbalderrama): do we have to implement hash/equals in Host?
    nodes = set([node.address for node in nodes])

    # Provision nodes so we can run Ansible on it
    api.exec_command_on_nodes(
        nodes,
        'apt-get update && apt-get -y --force-yes install python',
        'Installing python...')

    # Bind volumes of docker in /tmp (free storage location on G5k)
    api.exec_command_on_nodes(
        nodes,
        ('mkdir -p /tmp/docker/volumes; '
         'mkdir -p /var/lib/docker/volumes'),
        'Creating docker volumes directory in /tmp')
    api.exec_command_on_nodes(
        nodes,
        ('(mount | grep /tmp/docker/volumes) || '
         'mount --bind /tmp/docker/volumes /var/lib/docker/volumes'),
        'Bind mount')

    # Bind nova local storage in /tmp
    api.exec_command_on_nodes(
        nodes,
        'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
        'Creating nova directory in /tmp')
    api.exec_command_on_nodes(
        nodes,
        ('(mount | grep /tmp/nova) || '
         'mount --bind /tmp/nova /var/lib/nova'),
        'Bind mount')


class G5k(Provider):
    """Grid'5000 provider implementation.
    """

    def init(self, config, force=False):
        LOGGER.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(config)
        LOGGER.debug("Creating G5K provider")
        g5k = provider.G5k(enoslib_conf)
        LOGGER.info("Initializing G5K provider")
        roles, networks = g5k.init(force)
        _provision(roles)
        return roles, networks

    def destroy(self, env):
        conf = env.get('config')
        LOGGER.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(conf)
        LOGGER.debug("Creating G5K provider")
        g5k = provider.G5k(enoslib_conf)
        LOGGER.info("Destroying G5K deployment")
        g5k.destroy()

    def default_config(self):
        return {'job_name': 'Enos',
                'walltime': '02:00:00',
                'env_name': 'debian9-x64-min',
                'reservation': False,
                'user': 'root'}

    def __str__(self):
        return 'G5k'
