# -*- coding: utf-8 -*-
import copy
import logging

from enoslib.api import expand_groups
from enoslib.infra.enos_g5k import (provider, g5k_api_utils, remote)
from enoslib.infra.enos_g5k.configuration import Configuration

from enos.provider.provider import Provider
from enos.utils.extra import gen_enoslib_roles
from enos.utils.constants import (NETWORK_INTERFACE,
                                  NEUTRON_EXTERNAL_INTERFACE)


LOGGER = logging.getLogger(__name__)

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'job_name': 'Enos',             # Job name in oarstat/gant
    'walltime': '02:00:00',         # Reservation duration time
    'env_name': 'debian9-x64-nfs',  # Environment to deploy
    'reservation': '',           # Reservation date
    'job_type': 'deploy',           # deploy, besteffort, ...
    'queue': 'default'              # default, production, testing
}
# + SPHINX_DEFAULT_CONFIG

DEFAULT_CONN_PARAMS = {'user': 'root'}


PRIMARY_NETWORK = {
    "id": "int-net",
    "site": "rennes",
    "type": "kavlan",
    "roles": [NETWORK_INTERFACE]}

SECONDARY_NETWORK = {
    "id": "ext-net",
    "site": "rennes",
    "type": "kavlan",
    "roles": [NEUTRON_EXTERNAL_INTERFACE]}


def _count_common_interfaces(clusters):
    interfaces = g5k_api_utils.get_clusters_interfaces(clusters)
    return min([len(x) for x in interfaces.values()])


def _get_sites(clusters):
    clusters_sites = g5k_api_utils.get_clusters_sites(clusters)
    return set(clusters_sites.values())


def _build_enoslib_conf(config):
    conf = copy.deepcopy(config)
    enoslib_conf = conf.get("provider", {})
    enoslib_conf.pop("type", None)
    # NOTE(msimonin): Force some enoslib/g5k parameters here.
    # * dhcp: True means that network card will be brought up and the dhcp
    #   client will be called. As for now (2018-08-16) this is disabled by
    #   default in EnOSlib.
    enoslib_conf.update({
        "dhcp": True
    })

    if enoslib_conf.get("resources") is not None:

        # enoslib mode
        LOGGER.debug("Getting resources specific to the provider")
        return enoslib_conf

    # EnOS legacy mode
    LOGGER.debug("Getting generic resources from configuration")
    machines = []
    clusters = set()

    # get a plain configuration of resources
    resources = conf.get("resources", {})

    # when a topology configuration is present
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

    # check the location of the clusters
    sites = _get_sites(clusters)
    if len(sites) > 1:
        raise Exception("Multisite deployment isn't supported yet")

    site = sites.pop()
    PRIMARY_NETWORK["site"] = site
    SECONDARY_NETWORK["site"] = site
    networks = [PRIMARY_NETWORK]

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
    remote.exec_command_on_nodes(
        nodes,
        'apt-get update && apt-get -y --force-yes install python',
        'Installing python...')

    # Bind volumes of docker in /tmp (free storage location on G5k)
    remote.exec_command_on_nodes(
        nodes,
        ('mkdir -p /tmp/docker/volumes; '
         'mkdir -p /var/lib/docker/volumes'),
        'Creating docker volumes directory in /tmp')
    remote.exec_command_on_nodes(
        nodes,
        ('(mount | grep /tmp/docker/volumes) || '
         'mount --bind /tmp/docker/volumes /var/lib/docker/volumes'),
        'Bind mount')

    # Bind nova local storage in /tmp
    remote.exec_command_on_nodes(
        nodes,
        'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
        'Creating nova directory in /tmp')
    remote.exec_command_on_nodes(
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
        conf = Configuration.from_dictionnary(enoslib_conf)
        LOGGER.debug("Creating G5K provider")
        g5k = provider.G5k(conf)
        LOGGER.info("Initializing G5K provider")
        roles, networks = g5k.init(force)
        _provision(roles)
        return roles, networks

    def destroy(self, env):
        conf = env.get('config')
        LOGGER.debug("Building enoslib configuration")
        enoslib_conf = _build_enoslib_conf(conf)
        conf = Configuration.from_dictionnary(enoslib_conf)
        LOGGER.debug("Creating G5K provider")
        g5k = provider.G5k(conf)
        LOGGER.info("Destroying G5K deployment")
        g5k.destroy()

    def default_config(self):
        return DEFAULT_CONFIG

    def __str__(self):
        return 'G5k'
