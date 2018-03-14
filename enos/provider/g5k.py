# -*- coding: utf-8 -*-
from execo_g5k import api_utils as api
from execo_g5k import OarSubmission
from .host import Host
from itertools import islice
from netaddr import IPAddress, IPNetwork, IPSet
from provider import Provider
from ..utils.extra import build_roles, get_total_wanted_machines

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

        Read the resources in the configuration files.  Resource claims must be
        grouped by clusters available on Grid'5000.
        """
        _, vlans, nodes = self._get_jobs_and_vlans(conf)
        deployed, deployed_nodes_vlan = self._deploy(conf,
                                                     nodes,
                                                     vlans,
                                                     force_deploy=force_deploy)

        host_nodes = map(lambda n: Host(n.address, user="root"),
                         deployed_nodes_vlan)

        roles = build_roles(conf,
                            host_nodes,
                            lambda n: n.address.split('-')[0])

        network = self._get_network(vlans)
        network_interface, external_interface = \
            self._mount_cluster_nics(conf,
                                     conf['resources'].keys()[0],
                                     deployed,
                                     deployed_nodes_vlan,
                                     vlans)

        self._provision(deployed_nodes_vlan)

        return (roles, network, (network_interface, external_interface))

    def destroy(self, env):
        provider_conf = env['config']['provider']
        gridjob, _ = EX5.planning.get_job_by_name(provider_conf['name'])
        if gridjob is not None:
            EX5.oargriddel([gridjob])
            logging.info("Killing the job %s" % gridjob)

    def default_config(self):
        return {
            'name': 'Enos',
            'walltime': '02:00:00',
            'env_name': 'debian9-x64-nfs',
            'reservation': False,
            'vlans': {'rennes': "{type='kavlan'}/vlan=1"},
            'role_distribution': ROLE_DISTRIBUTION_MODE_STRICT,
            'single_interface': False,
            'user': 'root'
        }

    def __str__(self):
        return 'G5k'

    def _create_reservation(self, conf):
        """Create the OAR Job specs."""
        provider_conf = conf['provider']
        criteria = {}
        # NOTE(msimonin): Traverse all cluster demands in alphebetical order
        # test_create_reservation_different_site needs to know the order
        for cluster, roles in sorted(
                conf["resources"].items(),
                key=lambda x: x[0]):
            site = api.get_cluster_site(cluster)
            nb_nodes = reduce(operator.add, map(int, roles.values()))
            criterion = "{cluster='%s'}/nodes=%s" % (cluster, nb_nodes)
            criteria.setdefault(site, []).append(criterion)

        for site, vlan in provider_conf["vlans"].items():
            criteria.setdefault(site, []).append(vlan)

        # Compute the specification for the reservation
        jobs_specs = [(OarSubmission(resources='+'.join(c),
                                     name=provider_conf["name"]), s)
                      for s, c in criteria.items()]
        logging.info("Criteria for the reservation: %s" % pf(jobs_specs))
        return jobs_specs

    def _make_reservation(self, conf):
        """Make a new reservation."""
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
        """Get the hosts from an existing job (if any) or from a new job.
        This will perform a reservation if necessary."""

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
            vlan_id = EX5.get_oar_job_kavlan(job_id, site)
            if vlan_id is not None:
                vlans.append((site,
                                   EX5.get_oar_job_kavlan(job_id, site)))
        return (jobs, vlans, nodes)

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

    def _get_primary_vlan(self, vlans):
        """
        Returns the primary vlan
        It's the vlan where node are put in when deploying
        """
        vlan = None
        if len(vlans) > 0:
            # Each vlan is a pair of a name and a list of address.
            # Following picks the first vlan and changes the second
            # element of the pair to return the first address.
            vlan = (vlans[0][0], vlans[0][1][0])
            logging.info("Using vlan %s" % str(vlan))

        return vlan

    def _deploy(self, conf, nodes, vlans, force_deploy=False):
        provider_conf = conf['provider']
        # we put the nodes in the first vlan we have
        vlan = self._get_primary_vlan(vlans)
        # Deploy all the nodes
        logging.info("Deploying %s on %d nodes %s" % (
            provider_conf['env_name'],
            len(nodes),
            '(forced)' if force_deploy else ''))

        kw = {
            'hosts': nodes,
            'vlan': vlan[1],
        }
        if provider_conf.get('env_file'):
            kw.update({'env_file': provider_conf.get('env_file')})
        if provider_conf.get('env_name'):
            kw.update({'env_name': provider_conf.get('env_name')})

        deployed, undeployed = EX5.deploy(
            EX5.Deployment(**kw), check_deployed_command=not force_deploy)

        # Check the deployment
        if len(undeployed) > 0:
            logging.error("%d nodes where not deployed correctly:"
                          % len(undeployed))
            for n in undeployed:
                logging.error(n)

        deployed_nodes_vlan = sorted(
            self._translate_to_vlan(map(lambda n: EX.Host(n), deployed),
                                    vlan[1]),
            key=lambda n: n.address)

        logging.info(deployed_nodes_vlan)
        # Checking the deployed nodes according to the
        # resource distribution policy
        self._check_nodes(nodes=deployed_nodes_vlan,
                          resources=conf['resources'],
                          mode=conf['provider']['role_distribution'])

        return deployed, deployed_nodes_vlan

    def _get_network(self, vlans):
        """Gets the network representation.

        Prerequisite :
            - a vlan must be reserved

        """
        site, vlan_id = self._get_primary_vlan(vlans)

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

    def _mount_cluster_nics(self, conf, cluster, nodes, kavlan_nodes, vlans):
        """Get the NIC devices of the reserved cluster.

        :param nodes: List of hostnames unmodified by the vlan
        """
        provider_conf = conf['provider']
        # XXX: this only works if all nodes are on the same cluster,
        # or if nodes from different clusters have the same devices
        site = EX5.get_cluster_site(cluster)
        nics = EX5.get_resource_attributes(
            "/sites/%s/clusters/%s/nodes" % (site, cluster)
            )['items'][0]['network_adapters']

        interfaces = [nic['device'] for nic in nics
                                    if nic['mountable'] and
                                    nic['interface'] == 'Ethernet']

        network_interface = str(interfaces[0])
        external_interface = None

        if len(interfaces) > 1 and not provider_conf['single_interface']:
            external_interface = str(interfaces[1])
            _, vlan = self._get_primary_vlan(vlans)
            api.set_nodes_vlan(site,
                               map(lambda d: EX.Host(d), nodes),
                               external_interface,
                               vlan)

            self._exec_command_on_nodes(
                kavlan_nodes,
                "ifconfig %s up && dhclient -nw %s" % (
                    external_interface, external_interface),
                'mounting secondary interface')
        else:
            # TODO(msimonin) fix the network in this case as well.
            external_interface = 'veth0'
            if provider_conf['single_interface']:
                logging.warning("Forcing the use of a one network interface")
            else:
                logging.warning("%s has only one NIC. The same interface "
                                "will be used for network_interface and "
                                "neutron_external_interface."
                                % conf['resources'].keys()[0])

            self._exec_command_on_nodes(
                kavlan_nodes,
                'ip link show veth0 || ip link add type veth peer',
                'Creating a veth')

        return (network_interface, external_interface)

    def _exec_command_on_nodes(self, nodes, cmd, label, conn_params=None):
        """Execute a command on a node (id or hostname) or on a set of nodes"""
        if isinstance(nodes, basestring):
            nodes = [nodes]

        if conn_params is None:
            conn_params = DEFAULT_CONN_PARAMS

        logging.info(label)
        remote = EX.Remote(cmd, nodes, conn_params)
        remote.run()

        if not remote.finished_ok:
            raise Exception('An error occcured during remote execution')

    def _provision(self, nodes):
        # Provision nodes so we can run Ansible on it
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
