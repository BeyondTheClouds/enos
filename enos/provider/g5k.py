# -*- coding: utf-8 -*-
from provider import Provider
from ..utils.constants import ENOS_PATH, EXTERNAL_IFACE

import yaml
import os
import logging
import sys

# from string import Template
# from execo import configuration
import execo as EX
import execo_g5k as EX5
from execo_g5k import api_utils as api
from execo_g5k.api_utils import get_cluster_site
from execo_g5k import OarSubmission

from netaddr import IPNetwork, IPSet

from itertools import groupby
import operator

import pprint

NETWORK_FILE = os.path.join(ENOS_PATH, 'provider', 'g5k_networks.yaml')
ROLE_DISTRIBUTION_MODE_STRICT = "strict"
DEFAULT_CONFIG = {
    "name": "kolla-discovery",
    "walltime": "02:00:00",
    "env_name": 'ubuntu1404-x64-min',
    "reservation": None,
    "vlans": {},
    "role_distribution": ROLE_DISTRIBUTION_MODE_STRICT
}
MAX_ATTEMPTS = 5
DEFAULT_CONN_PARAMS = {'user': 'root'}

pf = pprint.PrettyPrinter(indent=4).pformat


class G5K(Provider):
    def init(self, config, force_deploy=False):
        """Provides resources and provisions the environment.

        Resources offers an ssh connection with an access for root
        user.

        The `config` parameter contains the client request (eg, number
        of compute per role among other things). This method returns a
        list of the form [{Role: [Host]}] and a pool of 5 ips.

        """
        self.config = DEFAULT_CONFIG
        self.config.update(config)

        self.force_deploy = force_deploy

        # Load g5k networks
        with open(NETWORK_FILE) as network_file:
            self.networks = yaml.load(network_file)

        self._get_job()

        deployed, undeployed = self._deploy()
        if len(undeployed) > 0:
            logging.error("Some of your nodes have been undeployed")
            sys.exit(31)

        roles = self._build_roles()

        # Get an IP for
        # kolla (haproxy)
        # docker registry
        # influx db
        # grafana
        vip_addresses, provider_network = self._get_free_ip(5)
        # Get the NIC devices of the reserved cluster
        # XXX: this only works if all nodes are on the same cluster,
        # or if nodes from different clusters have the same devices
        interfaces = self._get_cluster_nics(self.config['resources'].keys()[0])


        network_interface = str(interfaces[0])
        external_interface = None

        if len(interfaces) > 1 and not config['single_interface']:
            external_interface = str(interfaces[1])
            site, vlan = self._get_primary_vlan()
            # NOTE(msimonin) deployed is composed of the list of hostnames
            # unmodified with the vlan. This is required by set_nodes_vlan.
            api.set_nodes_vlan(site, map(lambda d: EX.Host(d), deployed), external_interface, vlan)

            self._exec_command_on_nodes(
                self.deployed_nodes,
                'ifconfig %s up && dhclient -nw %s' % (external_interface, external_interface),
                'mounting secondary interface'
             )
        else:
            # TODO(msimonin) fix the network in this case as well.
            external_interface = 'veth0'
            if config['single_interface']:
                logging.warning("Forcing the use of a single network interface")
            else:
                logging.warning("%s has only one NIC. The same interface "
                               "will be used for network_interface and "
                               "neutron_external_interface."
                               % self.config['resources'].keys()[0])

        self._exec_command_on_nodes(
            self.deployed_nodes,
            'apt-get update && apt-get -y --force-yes install apt-transport-https',
            'Installing apt-transport-https...')

        # Install python on the nodes
        self._exec_command_on_nodes(
            self.deployed_nodes,
            'apt-get -y install python',
            'Installing Python on all the nodes...')

        return (roles,
                map(str, vip_addresses),
                [network_interface, external_interface],
                provider_network)

    def before_preintsall(self, env):
        # Create a virtual interface for veth0 (if any)
        # - name: Installing bridge-utils
        #  apt: name=bridge-utils state=present
        #
        # - name: Creating virtual interface veth0
        #   shell: ip link show veth0 || ip link add type veth peer
        #
        # - name: Creating a bridge
        #   shell: brctl show | grep br0 || brctl addbr br0
        #
        # - name:  Setting IP {{ neutron_external_address }} for veth0
        #   shell: ip addr show | grep {{ neutron_external_address }}
        #          || ip addr add {{ neutron_external_address }} dev veth0
        #
        # - name: Turning veth0 up
        #   shell: ip link set veth0 up
        #
        # - name: Turning veth1 up
        #   shell: ip link set veth1 up
        #
        # - name: Connecting veth1 to br0
        #   shell: brctl addif br0 eth0
        #
        # - name: Connecting eth0 to br0
        #   shell: brctl addif br0 veth1
        #
        # - name: Turning br0 up
        #   shell: ifconfig br0 up
        nodes = sum(env['rsc'].values(), [])
        if env['eths'][EXTERNAL_IFACE] == 'veth0':
            self._exec_command_on_nodes(
                    nodes,
                    'ip link show veth0 || ip link add type veth peer',
                    'Creating a veth')

        # Bind volumes of docker
        self._exec_command_on_nodes(
                nodes,
                'mkdir -p /tmp/docker/volumes ; mkdir -p /var/lib/docker/volumes',
                'Creating docker volumes directory in /tmp')
        self._exec_command_on_nodes(
                nodes,
                '(mount | grep /tmp/docker/volumes) || mount --bind /tmp/docker/volumes /var/lib/docker/volumes',
                'Bind mount')

        # Bind nova local storage if there is any nova compute
        #
        # FIXME: This does the hypotheses that nova is installed under
        # compute node, but this is not necessarily. Nova could be
        # installed on whatever the user choose. For this reason it
        # will be a better strategy to parse the inventory file.
        if 'compute' in env['rsc']:
            self._exec_command_on_nodes(
                env['rsc']['compute'],
                'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
                'Creating nova directory in /tmp')
            self._exec_command_on_nodes(
                env['rsc']['compute'],
                '(mount | grep /tmp/nova) || mount --bind /tmp/nova /var/lib/nova',
                'Bind mount')

    def after_preintsall(self, env):
        pass

    def __str__(self):
        return 'G5K'

    def _make_reservation(self):
        """Make a new reservation."""

        # Extract the list of criteria (ie, `oarsub -l
        # *criteria*`) in order to compute a specification for the
        # reservation.
        criteria = {}
        # Actual criteria are :
        # - Number of node per site
        for cluster, roles in self.config["resources"].items():
            site = get_cluster_site(cluster)
            nb_nodes = reduce(operator.add, map(int, roles.values()))
            criterion = "{cluster='%s'}/nodes=%s" % (cluster, nb_nodes)
            criteria.setdefault(site, []).append(criterion)

        for site, vlan in self.config["vlans"].items():
            criteria.setdefault(site, []).append(vlan)

        # Compute the specification for the reservation
        jobs_specs = [(OarSubmission(resources='+'.join(c),
                                     name=self.config["name"]), s)
                      for s, c in criteria.items()]
        logging.info("Criteria for the reservation: %s" % pf(jobs_specs))

        # Make the reservation
        gridjob, _ = EX5.oargridsub(
            jobs_specs,
            reservation_date=self.config['reservation'],
            walltime=self.config['walltime'].encode('ascii', 'ignore'),
            job_type='deploy')

        # TODO - move this upper to not have a side effect here
        if gridjob is not None:
            self.gridjob = gridjob
            logging.info("Using new oargrid job %s" % self.gridjob)
        else:
            logging.error("No oar job was created.")
            sys.exit(26)

    def _check_nodes(self,
                     nodes=[],
                     resources={},
                     mode=ROLE_DISTRIBUTION_MODE_STRICT):
        "Do we have enough nodes according to the resources mode."
        wanted_nodes = 0
        for cluster, roles in resources.items():
            wanted_nodes += reduce(operator.add, map(int, roles.values()))

        if mode == ROLE_DISTRIBUTION_MODE_STRICT and wanted_nodes > len(nodes):
            raise Exception("Not enough nodes to continue")

        return True

    def _get_job(self):
        """Get the hosts from an existing job (if any) or from a new job.
        This will perform a reservation if necessary."""

        # Look if there is a running job or make a new reservation
        self.gridjob, _ = EX5.planning.get_job_by_name(self.config['name'])

        if self.gridjob is None:
            self._make_reservation()
        else:
            logging.info("Using running oargrid job %s" % self.gridjob)

        # Wait for the job to start
        EX5.wait_oargrid_job_start(self.gridjob)

        # # XXX Still useful?
        # attempts = 0
        # self.nodes = None
        # while self.nodes is None and attempts < MAX_ATTEMPTS:
        #     self.nodes = sorted(EX5.get_oargrid_job_nodes(self.gridjob),
        #                             key = lambda n: n.address)
        #     attempts += 1

        self.nodes = sorted(EX5.get_oargrid_job_nodes(self.gridjob),
                            key=lambda n: n.address)

        # # XXX check already done into `_deploy`.
        self._check_nodes(nodes=self.nodes,
                          resources=self.config['resources'],
                          mode=self.config['role_distribution'])

        # XXX(Ad_rien_) Start_date is never used, deadcode? - August
        # 11th 2016
        self.start_date = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'start_date' in job_info:
            self.start_date = job_info['start_date']

        # filling some information about the jobs here
        self.user = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'user' in job_info:
            self.user = job_info['user']

        # vlans information
        job_sites = EX5.get_oargrid_job_oar_jobs(self.gridjob)
        self.jobs = []
        self.vlans = []
        for (job_id, site) in job_sites:
            self.jobs.append((site, job_id))
            vlan_id = EX5.get_oar_job_kavlan(job_id, site)
            if vlan_id is not None:
                self.vlans.append((site,
                                   EX5.get_oar_job_kavlan(job_id, site)))

    def _translate_to_vlan(self, nodes, vlan_id):
        """When using a vlan, we need to *manually* translate
        the node name. We can't access nodes with their original names

        e.g : parapluie-1.rennes.grid5000.fr ->
        parapluie-1-kavlan-4.rennes.grid5000.fr

        """
        def translate(node):
            splitted = node.address.split(".")
            splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
            return EX.Host(".".join(splitted))

        return map(translate, nodes)

    def _get_primary_vlan(self):
        """
        Returns the primary vlan
        It's the vlan where node are put in when deploying
        """
        vlan = None
        if len(self.vlans) > 0:
            # Each vlan is a pair of a name and a list of address.
            # Following picks the first vlan and changes the second
            # element of the pair to return the first address.
            vlan = (self.vlans[0][0], self.vlans[0][1][0])
            logging.info("Using vlan %s" % str(vlan))
        return vlan

    def _deploy(self):
        # we put the nodes in the first vlan we have
        vlan = self._get_primary_vlan()
        # Deploy all the nodes
        logging.info("Deploying %s on %d nodes %s" % (self.config['env_name'],
            len(self.nodes),
            '(forced)' if self.force_deploy else ''))

        deployed, undeployed = EX5.deploy(
        EX5.Deployment(
            self.nodes,
            env_name=self.config['env_name'],
            vlan=vlan[1]
        ), check_deployed_command=not self.force_deploy)

        # Check the deployment
        if len(undeployed) > 0:
            logging.error("%d nodes where not deployed correctly:"
                          % len(undeployed))
            for n in undeployed:
                logging.error(n)

        # Updating nodes names with vlans
        self.nodes = sorted(
            self._translate_to_vlan(self.nodes, vlan[1]),
            key=lambda n: n.address)
        logging.info(self.nodes)
        self.deployed_nodes = sorted(
            self._translate_to_vlan(map(lambda n: EX.Host(n), deployed),
                                    vlan[1]),
            key=lambda n: n.address)
        logging.info(self.deployed_nodes)
        self._check_nodes(
                nodes=self.deployed_nodes,
                resources=self.config['resources'],
                mode=self.config['role_distribution'])

        return deployed, undeployed

    def _build_roles(self):
        """Returns a dict that maps each role to a list of G5K nodes::

          { 'controller': [paravance-1, paravance-5], 'compute':
        [econome-1] }

        """
        def mk_pools():
            "Indexes a node by its cluster to construct pools of nodes."
            pools = {}
            for cluster, nodes in groupby(
                    self.deployed_nodes, lambda node: node.address.split('-')[0]):
                pools.setdefault(cluster, []).extend(list(nodes))

            return pools

        def pick_nodes(pool, n):
            "Picks n node in a pool of nodes."
            nodes = pool[:n]
            del pool[:n]
            return nodes

        # Maps a role (eg, controller) with a list of G5K node
        roles_set = set()
        for roles in self.config['resources'].values():
            roles_set.update(roles.keys())
        roles = {k: [] for k in roles_set}
        roles_goal = {k: 0 for k in roles_set}

        # compute the aggregated number of nodes per roles
        for r in self.config['resources'].values():
            for k, v in r.items():
                roles_goal[k] = roles_goal[k] + v

        pools = mk_pools()
        for cluster, rs in self.config['resources'].items():
            current = pick_nodes(pools[cluster], 1)
            # distribute node into roles
            for r in rs.keys() * len(self.deployed_nodes):
                if current == []:
                    break
                if current != [] and len(roles[r]) < roles_goal[r]:
                    roles.setdefault(r, []).extend(current)
                    current = pick_nodes(pools[cluster], 1)

        logging.info("Roles: %s" % pf(roles))
        at_least_one = all(len(n) >= 1 for n in roles.values())
        if not at_least_one:
            # Even if we aren't in strict mode we garantee that
            # there will be at least on node per role
            raise Exception("Role doesn't have at least one node each")

        return roles

    def _get_free_ip(self, count):
        """
        Gets free ips and a provider network information used to create a
        flat network external network during the init phase.
        Originally it was done by reserving a subnet
        we now moves this implementation to a vlan based implementation

        Prerequisite :
            - a vlan must be reserved
            - g5k networks must be loaded before
        """
        vlan = self._get_primary_vlan()
        cidr = self.networks[vlan[0]]["vlans"][vlan[1]]
        logging.info("cidr : %s" % (cidr))
        range_ips = IPSet(IPNetwork(cidr)).iprange()
        # the last ip is reserved x.x.x.255, the previous one also
        # x.x.x..254 (gw), the x.x.x.253 seems to be pingable as well
        # (seems undocumented in g5k wiki)
        reserved = 3
        start_index = -3-count-1024
        end_index = -3-count-1
        provider_network = {
                'cidr': str(cidr),
                'start': str(range_ips[start_index]),
                'end': str(range_ips[end_index]),
                'gateway': str(range_ips[-2]),
                'dns': '131.254.203.235'
        }
        return list(range_ips[end_index+1:-reserved]), provider_network


    def _get_cluster_nics(self, cluster):
        site = EX5.get_cluster_site(cluster)
        nics = EX5.get_resource_attributes(
            '/sites/%s/clusters/%s/nodes'
            % (site, cluster))['items'][0]['network_adapters']
        return [nic['device'] for nic in nics if nic['mountable'] and nic['interface'] == 'Ethernet' ]

    def _exec_command_on_nodes(self, nodes, cmd, label, conn_params=None):
        """Execute a command on a node (id or hostname) or on a set of nodes"""
        if not isinstance(nodes, list):
            nodes = [nodes]

        if conn_params is None:
            conn_params = DEFAULT_CONN_PARAMS

        logging.info(label)
        remote = EX.Remote(cmd, nodes, conn_params)
        remote.run()

        if not remote.finished_ok:
            sys.exit(31)
