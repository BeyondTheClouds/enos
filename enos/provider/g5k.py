# -*- coding: utf-8 -*-
from execo_g5k import api_utils as api
from execo_g5k import OarSubmission
from .host import Host
from itertools import islice
from netaddr import IPAddress, IPNetwork, IPSet
from provider import Provider
from ..utils.extra import build_roles, get_total_wanted_machines

import copy
import execo as EX
import execo_g5k as EX5
import logging
import operator
import pprint


ROLE_DISTRIBUTION_MODE_STRICT = "strict"
MAX_ATTEMPTS = 5
DEFAULT_CONN_PARAMS = {'user': 'root'}

pf = pprint.PrettyPrinter(indent=4).pformat


class G5k(Provider):
    def init(self, conf, force_deploy=False):
        """enos up

        :param conf:         The configuration of the deployment.
        :param force_deploy: True iff nodes have to be redeployed.

        Read the resources in the configuration files.
        The workflow is :
        1) Get or create a new job using the information of the configuration.
        2he job contains nodes and vlans.
        2) Deploy a base environment on the reserved nodes, put them in the
        primary vlan.
        3) Put the other interfaces in the remaining vlans.
        4) Build and return the roles and the list of networks configured.
        """
        nodes, _, vlans = self._get_jobs_and_vlans(conf)
        primary_vlan, secondary_vlans = self._split_vlans(vlans)

        deployed, deployed_nodes_vlan = self._deploy(conf,
                nodes,
                vlan=primary_vlan,
                force_deploy=force_deploy)

        self._mount_cluster_nics(conf,
                                 deployed,
                                 deployed_nodes_vlan,
                                 secondary_vlans)

        self._provision(deployed_nodes_vlan)

        host_nodes = map(lambda n: Host(n.address, user="root"),
                         deployed_nodes_vlan)

        roles = build_roles(conf,
                            host_nodes,
                            lambda n: n.address.split('-')[0])

        networks = self._get_networks(primary_vlan, secondary_vlans)

        return (roles, networks)

    def destroy(self, env):
        """Destroys the resources by deleting the oargridjob."""
        provider_conf = env['config']['provider']
        gridjob, _ = EX5.planning.get_job_by_name(provider_conf['name'])
        if gridjob is not None:
            EX5.oargriddel([gridjob])
            logging.info("Killing the job %s" % gridjob)

    def default_config(self):
        """Default config of the G5K provider."""
        return {
            'name': 'Enos',
            'walltime': '02:00:00',
            'env_name': 'jessie-x64-min',
            'reservation': False,
            'role_distribution': ROLE_DISTRIBUTION_MODE_STRICT,
            'single_interface': False,
            'user': 'root',
            'networks': 2
        }

    def __str__(self):
        return 'G5k'

    def _split_vlans(self, vlans):
        """ Splits the vlan in primary one and secondary ones.

        Primary is used as default vlan in which to put nodes.
        Secondary vlans are those usable for the other network cards.

        :param vlans: list of tuple (site, [vlan_ids])

        Returns a tuple.
        - First element is a tupe (site, vlanids).
        - Second element is a list of tuple (site, [vlan_ids]).
        """
        s = sorted(copy.deepcopy(vlans))
        site, vlans = s.pop()
        primary = site, vlans.pop()
        secondaries = s
        if len(vlans) > 0:
            secondaries.append((site, vlans))
        return primary, secondaries

    def _create_reservation(self, conf):
        """Create the OAR Job specs.

        The oar reservation string is generated by this function.

        :param: the configuration of the deployment.

        Returns the job specs.
        """
        provider_conf = conf['provider']
        criteria = {}
        # Creates the nodes reservation specs
        # NOTE(msimonin): Traverse all cluster demands in alphebetical order
        # test_create_reservation_different_site needs to know the order
        for cluster, roles in sorted(
                conf["resources"].items(),
                key=lambda x: x[0]):
            site = api.get_cluster_site(cluster)
            nb_nodes = reduce(operator.add, map(int, roles.values()))
            criterion = "{cluster='%s'}/nodes=%s" % (cluster, nb_nodes)
            criteria.setdefault(site, []).append(criterion)

        # Creates the vlans reservation specs
        if provider_conf.get('vlans') is not None:
            # We assume the user know what he is doing, we just reserve what he
            # wants
            for site, vlan_desc in provider_conf['vlans'].items():
                criteria.setdefault(site, []).append(vlan_desc)
        else:
            # There will be as many vlans as interfaces or networks specified
            # in the configuration file.
            nsites = len(criteria.keys())
            max_usable_nics = self._get_max_usable_nics(conf)
            networks = provider_conf['networks']
            if networks > max_usable_nics:
                logging.warn("You requested %s networks" % networks)
                logging.warn("Only %s nics are available" % max_usable_nics)
            networks = min(networks, max_usable_nics)
            if nsites > 1:
                # We reserve as many global vlans as needed.
                # Note(msimonin): as for now (08/2017) there is only one global
                # vlan available on each g5k site
                # Note(msimonin): ideally we should be able to reserve a mix of
                # global/local vlans (not all the service communications needs
                # to span France)
                if networks > nsites:
                    logging.warn("You requested %s networks" % networks)
                    logging.warn("Only %s global vlans are available" % nsites)
                networks = min(nsites, max_usable_nics)
                for site, _ in zip(sorted(criteria.keys()),
                                   range(networks)):
                    criteria[site].append("{type='kavlan-global'}/vlan=1")
            else:
                # In the monosite case we reserve as many routed vlans as
                # needed Note(msimonin): There are (only) 6 routed vlans on
                # each site
                site = criteria.keys()[0]
                logging.info("Found %s max usable NICs" % max_usable_nics)
                criteria[site].append("{type='kavlan'}/vlan=%s" % networks)

        # Compute the specification for the reservation
        jobs_specs = [(OarSubmission(resources='+'.join(c),
                                     name=provider_conf["name"]), s)
                      for s, c in criteria.items()]
        logging.info("Criteria for the reservation: %s" % pf(jobs_specs))
        return jobs_specs

    def _get_max_usable_nics(self, conf):
        """ Compute the maximum usable network interfaces for the reservation.

        This is calculated by taking the minimum of the number of network cards
        available on each cluster of the reservation.

        :param conf: the configuration of the deployment.

        Returns the number of usable nics.
        """
        clusters = conf['resources'].keys()
        interfaces = self._get_clusters_interfaces(clusters)
        nics_number = min([len(x) for x in interfaces.values()])
        return nics_number

    def _get_clusters_interfaces(self, clusters, extra_cond=lambda nic: True):
        """ Returns for each cluster the available cluster interfaces

        :param clusters: list of the clusters.
        :param extra_cond: extra predicate to filter network card retrieved
        from the API. E.g lambda nic: not nic['mounted'] will retrieve all the
        usable network cards that are not mounted by default.

        Returns a dict of cluster: [nic_names]
        """
        interfaces = {}
        for cluster in clusters:
            site = EX5.get_cluster_site(cluster)
            nics = EX5.get_resource_attributes(
                "/sites/%s/clusters/%s/nodes" % (site, cluster))
            nics = nics['items'][0]['network_adapters']
            nics = [nic['device'] for nic in nics
                   if nic['mountable'] and
                   nic['interface'] == 'Ethernet' and
                   not nic['management'] and extra_cond(nic)]
            nics = sorted(nics)
            interfaces.setdefault(cluster, nics)
        logging.info(interfaces)
        return interfaces

    def _make_reservation(self, conf):
        """Make a new reservation.

        :param conf: the configuration of the deployment.

        Returns the grijob.
        """
        provider_conf = conf['provider']
        jobs_specs = self._create_reservation(conf)
        # Make the reservation
        gridjob, _ = EX5.oargridsub(
            jobs_specs,
            reservation_date=provider_conf['reservation'],
            walltime=provider_conf['walltime'].encode('ascii', 'ignore'),
            job_type='deploy')

        if gridjob is None:
            raise Exception('No oar job was created')
        logging.info("Using new oargrid job %s" % gridjob)

        return gridjob

    def _check_nodes(self,
                     nodes=None,
                     resources={},
                     mode=ROLE_DISTRIBUTION_MODE_STRICT):
        "Do we have enough nodes according to the resources mode."
        nodes = nodes or []
        wanted_nodes = get_total_wanted_machines(resources)

        if mode == ROLE_DISTRIBUTION_MODE_STRICT and wanted_nodes > len(nodes):
            raise Exception("Not enough nodes to continue")

        return True

    def _get_jobs_and_vlans(self, conf):
        """Get the ressources (hosts, vlans) from an existing job (if any) or
        from a new job.

        This will perform a reservation if necessary.

        :param conf: the configuration of the deployment.

        Returns a tuple (nodes, jobs, vlans) where :
        - nodes is a list of reserved node in grid5000 (canonical names)
        - jobs is a list of tuple (site, job_id)
        - vlans is a list of tuple (site, [vlan_ids])
        """

        provider_conf = conf['provider']
        # Look if there is a running job or make a new reservation
        gridjob, _ = EX5.planning.get_job_by_name(provider_conf['name'])

        if gridjob is None:
            gridjob = self._make_reservation(conf)
        else:
            logging.info("Using running oargrid job %s" % gridjob)

        # Wait for the job to start
        EX5.wait_oargrid_job_start(gridjob)

        nodes = sorted(EX5.get_oargrid_job_nodes(gridjob),
                            key=lambda n: n.address)

        # Checking the number of nodes given
        # the disribution policy
        self._check_nodes(nodes=nodes,
                          resources=conf['resources'],
                          mode=provider_conf['role_distribution'])

        # vlans information
        job_sites = EX5.get_oargrid_job_oar_jobs(gridjob)
        jobs = []
        vlans = []
        for (job_id, site) in job_sites:
            jobs.append((site, job_id))
            vlan_ids = sorted(EX5.get_oar_job_kavlan(job_id, site))
            if vlan_ids is not None:
                vlans.append((site, vlan_ids))
        return (nodes, jobs, vlans)

    def _translate_to_vlan(self, nodes, vlan_id):
        """When using a vlan, we need to *manually* translate
        the node name. We can't access nodes with their canonical names.

        e.g : parapluie-1.rennes.grid5000.fr ->
        parapluie-1-kavlan-4.rennes.grid5000.fr.
        """
        def translate(node):
            splitted = node.address.split(".")
            splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
            return EX.Host(".".join(splitted))

        return map(translate, nodes)

    def _deploy(self, conf, nodes, vlan, force_deploy=False):
        provider_conf = conf['provider']
        logging.info("Deploying %s on %d nodes %s in vlan %s" % (
            provider_conf['env_name'],
            len(nodes),
            vlan,
            '(forced)' if force_deploy else ''))

        deployed, undeployed = EX5.deploy(
            EX5.Deployment(
                nodes,
                vlan=vlan[1],
                env_name=provider_conf['env_name'],
            ), check_deployed_command=not force_deploy)

        # Check the deployment
        if len(undeployed) > 0:
            logging.error("%d nodes where not deployed correctly:"
                          % len(undeployed))
            for n in undeployed:
                logging.error(n)
        deployed = [n for n in nodes if n.address in deployed]
        deployed = sorted(deployed, key=lambda n: n.address)
        deployed_nodes_vlan = self._translate_to_vlan(deployed, vlan[1])
        deployed_nodes_vlan = [EX.Host(h.address) for h in deployed_nodes_vlan]

        logging.info("Deployed nodes %s " % deployed)
        # Checking the deployed nodes according to the
        # resource distribution policy
        self._check_nodes(nodes=deployed,
                          resources=conf['resources'],
                          mode=conf['provider']['role_distribution'])

        return deployed, deployed_nodes_vlan

    def _get_networks(self, primary_vlan, secondary_vlans):
        """Gets the list of network configured during the init phase.

        :param vlans: list of tuple (site, [vlandids]).

        Returns the list of configured networks.
        """
        def get_net(site, vlan_id):
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
            # kavlan in G5k wiki.
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

        networks = []
        # Making sure the primary network is the firts on the network list
        site, vlan_id = primary_vlan
        networks.append(get_net(site, vlan_id))

        for site, vlan_ids in secondary_vlans:
            for vlan_id in vlan_ids:
                # Get g5k networks. According to the documentation, this
                # network is a `/18`.
                networks.append(get_net(site, vlan_id))
        return networks

    def _mount_cluster_nics(self, conf, nodes, nodes_vlans, sites_vlans):
        """
        Put each network interface of nodes in a dedicated vlan.

        :param conf:        the configuration of the deployment.
        :param nodes:       the list of execo.Host reserved nodes (canonical
                            names).
        :param nodes_vlans: the list of execo.Host reserved nodes (primary vlan
                            names)
        :param sites_vlans: list of vlans reserved by site (site -> [vlanids])
        """
        if not sites_vlans:
            # Avoiding calls to the apis
            return

        clusters_interfaces = self._get_clusters_interfaces(
            conf['resources'].keys(),
            lambda nic: not nic['mounted'])
        vlan_nodes = {}
        for site, vlans in sites_vlans:
            for cluster, nics in clusters_interfaces.items():
                nodes_to_set = [n for n in nodes
                        if n.address.split('-')[0] == cluster and
                        n.address.split('.')[1] == site]
                vlan_idx = 0
                for vlan in sorted(vlans):
                    nic = nics[vlan_idx]
                    api.set_nodes_vlan(site,
                                       nodes_to_set,
                                       nic,
                                       vlan)
                    vlan_idx = vlan_idx + 1
                    self._exec_command_on_nodes(
                        nodes_vlans,
                        "ifconfig %s up && dhclient -nw %s" % (
                            nic, nic),
                        'mounting secondary interface')
                    # keep the dns name of nodes
                    vlan_nodes.setdefault(vlan, [])
                    vlan_nodes[vlan].append(
                        self._translate_to_vlan(nodes, vlan))

        return vlan_nodes

    def _exec_command_on_nodes(self, nodes, cmd, label, conn_params=None):
        """Execute a command on a node (id or hostname) or on a set of nodes.

        :param nodes:       list of targets of the command cmd. Each must be an
                            execo.Host.
        :param cmd:         string representing the command to run on the
                            remote nodes.
        :param label:       string for debugging purpose.
        :param conn_params: connection parameters passed to the execo.Remote
                            function
       """
        if isinstance(nodes, basestring):
            nodes = [nodes]

        if conn_params is None:
            conn_params = DEFAULT_CONN_PARAMS

        logging.info("Running %s on %s " % (label, nodes))
        remote = EX.Remote(cmd, nodes, conn_params)
        remote.run()

        if not remote.finished_ok:
            raise Exception('An error occcured during remote execution')

    def _provision(self, nodes):
        """Provision the freshly acquired nodes."""
        self._exec_command_on_nodes(
            nodes,
            'apt-get update && apt-get -y --force-yes install python',
            'Installing python...')

        # Bind volumes of docker in /tmp (free storage location on G5k)
        self._exec_command_on_nodes(
            nodes,
            ('mkdir -p /tmp/docker/volumes; '
             'mkdir -p /var/lib/docker/volumes'),
            'Creating docker volumes directory in /tmp')

        self._exec_command_on_nodes(
            nodes,
            ('(mount | grep /tmp/docker/volumes) || '
             'mount --bind /tmp/docker/volumes /var/lib/docker/volumes'),
            'Bind mount')

        # Bind nova local storage in /tmp
        self._exec_command_on_nodes(
            nodes,
            'mkdir -p /tmp/nova ; mkdir -p /var/lib/nova',
            'Creating nova directory in /tmp')
        self._exec_command_on_nodes(
            nodes,
            '(mount | grep /tmp/nova) || mount --bind /tmp/nova /var/lib/nova',
            'Bind mount')
