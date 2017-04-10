# -*- coding: utf-8 -*-
from execo_g5k import api_utils as api
from execo_g5k.api_utils import get_cluster_site
from execo_g5k import OarSubmission
from .host import Host
from itertools import islice
from netaddr import IPAddress, IPNetwork, IPSet
from provider import Provider
from ..utils.extra import build_resources, expand_topology, build_roles
from ..utils.constants import EXTERNAL_IFACE

import execo as EX
import execo_g5k as EX5
import logging
import operator
import pprint
import sys


ROLE_DISTRIBUTION_MODE_STRICT = "strict"
DEFAULT_CONFIG = {
    "name": "kolla-discovery",
    "walltime": "02:00:00",
    "env_name": 'jessie-x64-min',
    "reservation": None,
    "vlans": {},
    "role_distribution": ROLE_DISTRIBUTION_MODE_STRICT,
    "single_interface": False
}
MAX_ATTEMPTS = 5
DEFAULT_CONN_PARAMS = {'user': 'root'}
QUEUE_PRIORITIES = ['default', 'production', 'testing']

pf = pprint.PrettyPrinter(indent=4).pformat


class G5k(Provider):
    def init(self, config, calldir, force_deploy=False):
        """python -m enos.enos up --provider=g5k

        Read the resources in the configuration files.  Resource claims must be
        grouped by clusters available on Grid'5000.
        """
        self._load_config(config)
        self.force_deploy = force_deploy
        self._get_jobs()
        deployed, undeployed = self._deploy()
        if len(undeployed) > 0:
            logging.error("Some of your nodes have been undeployed")
            sys.exit(31)

        # Provision nodes so we can run Ansible on it
        self._exec_command_on_nodes(
            self.deployed_nodes,
            'apt-get update && apt-get -y --force-yes install %s'
            % ' '.join(['apt-transport-https',
                        'python',
                        'python-setuptools']),
            'Installing apt-transport-https python...')

        # fix installation of pip on jessie
        self._exec_command_on_nodes(
            self.deployed_nodes,
            'easy_install pip && ln -s /usr/local/bin /usr/bin/pip || true',
            'Installing pip')

        # Retrieve necessary information for enos
        roles = build_roles(
                    self.config,
                    map(lambda n: Host(n.address, user="root"), self.deployed_nodes),
                    lambda n: n.address.split('-')[0])
        network = self._get_network()
        network_interface, external_interface = \
            self._mount_cluster_nics(
                self.config['resources'].keys()[0],
                deployed)

        return (roles, network, (network_interface, external_interface))

    def destroy(self, calldir, env):
        self._load_config(env['config'])
        self._get_job_ids()

        if self.gridjobs is not None:
            EX5.oargriddel(self.gridjobs)
        logging.info("Killed jobs %s" % self.gridjobs)

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
        nodes = map(lambda n: EX.Host(n.address), sum(env['rsc'].values(), []))
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
        computes = map(lambda n: EX.Host(n.address), env['rsc'].get('compute', []))
        self._exec_command_on_nodes(
            computes,
            'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
            'Creating nova directory in /tmp')
        self._exec_command_on_nodes(
            computes,
            '(mount | grep /tmp/nova) || mount --bind /tmp/nova /var/lib/nova',
            'Bind mount')

    def after_preintsall(self, env):
        pass

    def __str__(self):
        return 'G5k'

    def _make_reservation(self):
        """Make a new reservation."""

        # Extract the list of criteria (ie, `oarsub -l
        # *criteria*`) in order to compute a specification for the
        # reservation.
        criteria = {}
        # Actual criteria are :
        # - Number of node per site
        queues = self._get_queues()
        for queue, clusters in queues.iteritems():
            criteria[queue] = {}

            for cluster, roles in self.config["resources"].items():
                if not cluster in clusters:
                    continue

                site = get_cluster_site(cluster)
                nb_nodes = reduce(operator.add, map(int, roles.values()))
                criterion = "{cluster='%s'}/nodes=%s" % (cluster, nb_nodes)
                criteria[queue].setdefault(site, []).append(criterion)

        # Add a vlan to the first queue that contains a matching site
        for site, vlan in self.config["vlans"].items():
            for queue, qc in criteria.iteritems():
                if site in qc.keys():
                    criteria[queue][site].append(vlan)
                    break

        # Make one reservation per queue
        self.gridjobs = []
        for queue in queues:
            # Compute the specification for the reservation
            name = self._get_job_name(len(self.gridjobs))
            jobs_specs = [(OarSubmission(resources='+'.join(c),
                                         name=name,
                                         queue=queue), s)
                          for s, c in criteria[queue].items()]
            logging.info("Criteria for the reservation: %s" % pf(jobs_specs))

            # Make the reservation
            gridjob, _ = EX5.oargridsub(
                jobs_specs,
                reservation_date=self.config['reservation'],
                walltime=self.config['walltime'].encode('ascii', 'ignore'),
                job_type='deploy',
                queue=queue)

            # TODO - move this upper to not have a side effect here
            if gridjob is not None:
                self.gridjobs.append(gridjob)
                logging.info("Using new oargrid job %s" % gridjob)
            else:
                logging.error("No oar job was created.")
                if len(self.gridjobs) > 0:
                    EX5.oargriddel(self.gridjobs)
                    logging.error("Deleting already submitted jobs: %s" % self.gridjobs)
                sys.exit(26)


    def _get_queues(self):
        try:
            return self._queues
        except AttributeError:
            pass

        self._queues = {}

        for cluster, roles in self.config["resources"].items():
            site = get_cluster_site(cluster)

            # Select the appropriate queue for the cluster
            resources = EX5.get_resource_attributes('/sites/%s/clusters/%s' % (site, cluster))
            queue = None
            for q in QUEUE_PRIORITIES:
                if q in resources['queues']:
                    queue = q
                    break

            # This allows to use the 'admin' queue in last resort
            if queue is None:
                queue = resources['queues'][0]
                logging.warning("Using queue %s for cluster %s" % (queue, cluster))

            self._queues.setdefault(queue, []).append(cluster)

        if len(self._queues) > 1:
            logging.warning("Your request requires %d jobs in as many queues"
                    % len(self._queues))
        logging.info("Queues: " + str(self._queues))
        return self._queues

    def _load_config(self, config):
        self.config = DEFAULT_CONFIG
        self.config.update(config)
        if 'topology' in self.config:
            # expand the groups first
            self.config['topology'] = expand_topology(self.config['topology'])
            # Build the ressource claim to g5k
            # We are here using a flat combination of the resource
            # resulting in (probably) deploying one single region
            self.config['resources'] = build_resources(self.config['topology'])

    def _check_nodes(self,
                     nodes=[],
                     resources={},
                     mode=ROLE_DISTRIBUTION_MODE_STRICT):
        "Do we have enough nodes according to the resources mode."
        wanted_nodes = 0
        for cluster, roles in resources.items():
            wanted_nodes += reduce(operator.add, map(int, roles.values()))

        if mode == ROLE_DISTRIBUTION_MODE_STRICT and wanted_nodes > len(nodes):
            raise Exception("Not enough nodes to continue (%d missing)"
                    % (wanted_nodes - len(nodes)))

        return True


    def _get_job_name(self, id):
        return "%s-%d" % (self.config['name'], id)


    def _get_job_ids(self):
        """Get the ids of running jobs (if any).
        This method looks for a certain number of oargrid jobs depending
        on the number of queues required by the configuration.

        If the exact number of jobs is found, this method assings an array
        of job ids to `self.gridjobs` and returns it. If no job is found,
        this method returns `None`. If the number of jobs found is more
        than zero but less than the required number, this method quits
        the program and prints the ids of the found jobs.
        """
        queues = self._get_queues()
        jobs = []

        for i in range(len(queues)):
            name = self._get_job_name(i)
            job, _ = EX5.planning.get_job_by_name(name)
            if job is not None:
                jobs.append(job)
            else:
                break

        if len(jobs) == 0:
            self.gridjobs = None
        elif len(jobs) == len(queues):
            self.gridjobs = jobs
        else:
            logging.error("There are some missing jobs. I found %s" % str(jobs))
            sys.exit(21)

        return self.gridjobs


    def _get_jobs(self):
        """Get the hosts from existing jobs (if any) or from new jobs.
        This will perform reservations if necessary."""

        # Look if there is a running job or make a new reservation
        self._get_job_ids()

        if self.gridjobs is None:
            self._make_reservation()
        else:
            logging.info("Using running oargrid jobs %s" % self.gridjobs)

        # Wait for the jobs to start
        nodes = []
        for job_id in self.gridjobs:
            EX5.wait_oargrid_job_start(job_id)
            nodes += EX5.get_oargrid_job_nodes(job_id)

        self.nodes = sorted(nodes, key=lambda n: n.address)
        logging.info(nodes)

        # XXX check already done into `_deploy`.
        self._check_nodes(nodes=nodes,
                          resources=self.config['resources'],
                          mode=self.config['role_distribution'])

        # filling some information about the jobs here
        self.user = None
        # FIXME is this correct?
        job_info = EX5.get_oargrid_job_info(self.gridjobs[0])
        if 'user' in job_info:
            self.user = job_info['user']

        # vlans information
        job_sites = reduce(operator.add, map(EX5.get_oargrid_job_oar_jobs, self.gridjobs))

        self.jobs = []
        self.vlans = []
        for (job_id, site) in job_sites:
            self.jobs.append((site, job_id))

            vlan_id = EX5.get_oar_job_kavlan(job_id, site)
            if vlan_id is not None:
                 self.vlans.append((site, vlan_id))

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
        logging.info("Deploying %s on %d nodes %s" % (
            self.config['env_name'],
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

    def _get_network(self):
        """Gets the network representation.

        Prerequisite :
            - a vlan must be reserved

        """
        site, vlan_id = self._get_primary_vlan()

        # Get g5k networks. According to the documentation, this
        # network is a `/18`.
        site_info = EX5.get_resource_attributes('/sites/%s' % site)
        net = site_info['kavlans'][str(vlan_id)]
        logging.info("cidr : %s" % net['network'])

        # On the network, the first IP are reserved to g5k machines.
        # For a routed vlan I don't know exactly how many ip are
        # reserved. However, the specification is clear about global
        # vlan: "A global VLAN is a /18 subnet (16382 IP addresses).
        # It is split -- contiguously -- so that every site gets one
        # /23 (510 ip) in the global VLAN address space". There are 12
        # site. This means that we could take ip from 13th subnetwork.
        # Lets consider the strategy is the same for routed vlan. See,
        # https://www.grid5000.fr/mediawiki/index.php/Grid5000:Network#KaVLAN
        #
        # First, split network in /23 this leads to 32 subnetworks.
        subnets = IPNetwork(net['network']).subnet(23)

        # Then, (i) drops the 12 first subnetworks because they are
        # dedicated to g5k machines, and (ii) drops the last one
        # because some of ips are used for specific stuff such as
        # gateway, kavlan server...
        subnets = islice(subnets, 13, 31)

        # Finally, compute the range of available ips
        ips = IPSet(subnets).iprange()

        return {
            'cidr': str(net['network']),
            'start': str(IPAddress(ips.first)),
            'end': str(IPAddress(ips.last)),
            'gateway': str(net['gateway']),
            'dns': '131.254.203.235'
        }

    def _mount_cluster_nics(self, cluster, nodes):
        """Get the NIC devices of the reserved cluster.

        :param nodes: List of hostnames unmodified by the vlan
        """
        # XXX: this only works if all nodes are on the same cluster,
        # or if nodes from different clusters have the same devices
        site = EX5.get_cluster_site(cluster)
        nics = EX5.get_resource_attributes(
            "/sites/%s/clusters/%s/nodes" % (site, cluster)
            )['items'][0]['network_adapters']

        interfaces = [nic['device'] for nic in nics
                                    if nic['mountable']
                                    and nic['interface'] == 'Ethernet']

        network_interface = str(interfaces[0])
        external_interface = None

        if len(interfaces) > 1 and not self.config['single_interface']:
            external_interface = str(interfaces[1])
            _, vlan = self._get_primary_vlan()
            api.set_nodes_vlan(site,
                               map(lambda d: EX.Host(d), nodes),
                               external_interface,
                               vlan)

            self._exec_command_on_nodes(
                self.deployed_nodes,
                "ifconfig %s up && dhclient -nw %s" % (
                    external_interface, external_interface),
                'mounting secondary interface')
        else:
            # TODO(msimonin) fix the network in this case as well.
            external_interface = 'veth0'
            if self.config['single_interface']:
                logging.warning("Forcing the use of a one network interface")
            else:
                logging.warning("%s has only one NIC. The same interface "
                                "will be used for network_interface and "
                                "neutron_external_interface."
                                % self.config['resources'].keys()[0])

        return (network_interface, external_interface)

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
