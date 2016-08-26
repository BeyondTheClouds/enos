import pprint, os, sys
pf = pprint.PrettyPrinter(indent=4).pformat
import yaml

import execo as EX
from string import Template
from execo import configuration
from execo.log import style
import execo_g5k as EX5
from execo_g5k.api_utils import get_cluster_site
from execo_g5k import OarSubmission
from execo_engine import Engine, logger

from itertools import groupby
from netaddr import IPNetwork, IPSet
import operator

# Default values
DEFAULT_CONF_FILE = 'reservation.yaml'
NETWORK_FILE = 'g5k_networks.yaml'

MAX_ATTEMPTS = 5

DEFAULT_CONN_PARAMS = {'user': 'root'}

ROLE_DISTRIBUTION_MODE_STRICT = "strict"

DEFAULT_CONFIG = {
    "name": "kolla-discovery",
    "walltime": "02:00:00",
    "env_name": 'ubuntu1404-x64-min',
    "reservation": None,
    "vlans": {},
    "role_distribution": ROLE_DISTRIBUTION_MODE_STRICT
};

def translate_to_vlan(nodes, vlan_id):
    """
    When using a vlan, we need to *manually* translate
    the node name. We can't access nodes with their original names
    e.g : parapluie-1.rennes.grid5000.fr -> parapluie-1-kavlan-4.rennes.grid5000.fr

    """
    def translate(node):
        splitted = node.address.split(".")
        splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
        return EX.Host(".".join(splitted))
    return map(translate, nodes)

def check_nodes(nodes = [], resources = {}, mode = ROLE_DISTRIBUTION_MODE_STRICT):
    """
    Do we have enough nodes according to the
    - resources
    - mode
    """
    wanted_nodes = 0
    for cluster, roles in resources.items():
        wanted_nodes += reduce(operator.add, map(int, roles.values()))

    if mode == ROLE_DISTRIBUTION_MODE_STRICT and wanted_nodes > len(nodes):
        raise Exception("Not enough nodes to continue")

    return True

class G5kEngine(Engine):
    def __init__(self, conf_file, force_deploy):
        """Initialize the Execo Engine"""
        super(G5kEngine, self).__init__()

        self.config_path = conf_file
        self.force_deploy = force_deploy

    def load(self):
        """Load the configuration file"""

        # Load the configuration file
        try:
            with open(self.config_path) as config_file:
                config = yaml.load(config_file)
        except:
            logger.error("Error reading configuration file %s" %
                         self.config_path)
            t, value, tb = sys.exc_info()
            print("%s %s" % (str(t), str(value)))
            sys.exit(23)

        # Load g5k networks
        with open(NETWORK_FILE) as network_file:
            self.networks = yaml.load(network_file)


        self.config = {}
        self.config.update(DEFAULT_CONFIG)
        self.config.update(config)

        logger.info("Configuration file loaded : %s" % self.config_path)
        logger.info(pf(self.config))

        return self.config

    def get_job(self):
        """Get the hosts from an existing job (if any) or from a new job.
        This will perform a reservation if necessary."""

        # Look if there is a running job or make a new reservation
        self.gridjob, _ = EX5.planning.get_job_by_name(self.config['name'])

        if self.gridjob is None:
            self._make_reservation()
        else:
            logger.info("Using running oargrid job %s" % style.emph(self.gridjob))

        attempts = 0
        self.nodes = None
        while self.nodes is None and attempts < MAX_ATTEMPTS:
            self.nodes = sorted(EX5.get_oargrid_job_nodes(self.gridjob),
                                    key = lambda n: n.address)
            attempts += 1

        check_nodes(
                nodes = self.nodes,
                resources = self.config['resources'],
                mode = self.config['role_distribution'])

        # TODO - Start_date is never used, deadcode ? Ad_rien_ - August 11th 2016
        self.start_date = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'start_date' in job_info:
            self.start_date = job_info['start_date']

        ## filling some information about the jobs here
        self.user = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'user' in job_info:
            self.user = job_info['user']

        ## vlans information
        job_sites = EX5.get_oargrid_job_oar_jobs(self.gridjob)
        self.jobs = []
        self.vlans = []
        for (job_id, site) in job_sites:
            self.jobs.append((site, job_id))
            vlan_id = EX5.get_oar_job_kavlan(job_id, site)
            if vlan_id is not None:
                self.vlans.append((site, EX5.get_oar_job_kavlan(job_id, site)))

        return self.gridjob

    def deploy(self):
        # we put the nodes in the first vlan we have
        vlan = self._get_primary_vlan()
         # Deploy all the nodes
        logger.info("Deploying %s on %d nodes %s" % (self.config['env_name'],
            len(self.nodes),
            '(forced)' if self.force_deploy else ''))

        deployed, undeployed = EX5.deploy(
        EX5.Deployment(
            self.nodes,
            env_name=self.config['env_name'],
            vlan = vlan[1]
        ), check_deployed_command=not self.force_deploy)

        # Check the deployment
        if len(undeployed) > 0:
            logger.error("%d nodes where not deployed correctly:" % len(undeployed))
            for n in undeployed:
                logger.error(style.emph(undeployed.address))

        # Updating nodes names with vlans
        self.nodes = sorted(translate_to_vlan(self.nodes, vlan[1]),
                            key = lambda n: n.address)
        logger.info(self.nodes)
        self.deployed_nodes = sorted(translate_to_vlan(
                                        map(lambda n: EX.Host(n), deployed), vlan[1]),
                                key = lambda n: n.address)
        logger.info(self.deployed_nodes)
        check_nodes(
                nodes = self.deployed_nodes,
                resources = self.config['resources'],
                mode = self.config['role_distribution'])

        return deployed, undeployed

    def exec_command_on_nodes(self, nodes, cmd, label, conn_params=None):
        """Execute a command on a node (id or hostname) or on a set of nodes"""
        if not isinstance(nodes, list):
            nodes = [nodes]

        if conn_params is None:
            conn_params = DEFAULT_CONN_PARAMS

        logger.info(label)
        remote = EX.Remote(cmd, nodes, conn_params)
        remote.run()

        if not remote.finished_ok:
            sys.exit(31)

    def build_roles(self):
        """
        Returns a dict that maps each role to a list of G5K nodes::

          { 'controller': [paravance-1, paravance-5], 'compute': [econome-1] }
        """
        def mk_pools():
            "Indexes each node by its cluster to construct pools of nodes."
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
            for k,v in r.items():
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

        logger.info("Roles: %s" % pf(roles))
        at_least_one = all(len(n) >= 1 for n in roles.values())
        if not at_least_one:
            # Even if we aren't in strict mode we garantee that
            # there will be at least on node per role
            raise Exception("Role doesn't have at least one node each")

        return roles


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
        jobs_specs = [(OarSubmission(resources = '+'.join(c),
                                     name = self.config["name"]), s)
                      for s, c in criteria.items()]
        logger.info("Criteria for the reservation: %s" % pf(jobs_specs))

        # Make the reservation
        gridjob, _ = EX5.oargridsub(
            jobs_specs,
            reservation_date=self.config['reservation'],
            walltime=self.config['walltime'].encode('ascii', 'ignore'),
            job_type='deploy'
        )

        # TODO - move this upper to not have a side effect here
        if gridjob is not None:
            self.gridjob = gridjob
            logger.info("Using new oargrid job %s" % style.emph(self.gridjob))
        else:
            logger.error("No oar job was created.")
            sys.exit(26)

    def get_free_ip(self, count):
        """
        Gets a free ip.
        Originally it was done by reserving a subnet
        we now moves this implementation to a vlan based implementation

        Prerequisite :
            - a vlan must be reserved
            - g5k networks must be loaded before
        """
        vlan = self._get_primary_vlan()
        cidr = self.networks[vlan[0]]["vlans"][vlan[1]]
        logger.info("cidr : %s" % (cidr))
        range_ips = IPSet(IPNetwork(cidr)).iprange()
        # the last ip is reserved x.x.x.255
        # the previous one also x.x.x..254 (gw)
        # the x.x.x.253 seems to be pingable as well (seems undocumented in g5k wiki)
        return list(range_ips[-3-count:-3])

    def get_cluster_nics(self, cluster):
        site = EX5.get_cluster_site(cluster)
        nics = EX5.get_resource_attributes('/sites/%s/clusters/%s/nodes' % (site, cluster))['items'][0]['network_adapters']
        return [nic['device'] for nic in nics if nic['mountable']]

    def delete_job(self):
        EX5.oardel([self.gridjob])

    def generate_sshtunnels(self, internal_vip_address):
        logger.info("ssh tunnel informations:")
        logger.info("___")

        script = "cat > /tmp/openstack_ssh_config <<EOF\n"
        script += "Host *.grid5000.fr\n"
        script += "  User " + self.user + " \n"
        script += "  ProxyCommand ssh -q " + self.user + "@194.254.60.4 nc -w1 %h %p # Access South\n"
        script += "EOF\n"

        port = 8080
        script += "ssh -F /tmp/openstack_ssh_config -N -L " + str(port) + ":" + internal_vip_address + ":80 " + self.user + "@access.grid5000.fr &\n"

        script += "echo 'http://localhost:8080'\n"
        logger.info(script)
        logger.info("___")

        with open(self.result_dir + "/dashboard_tunnels.sh", 'w') as f:
            f.write(script)

        logger.info("ssh tunnel informations:")
        logger.info("___")

    def _get_primary_vlan(self):
        """
        Returns the primary vlan
        It's the vlan where node are put in when deploying
        """
        vlan = None
        if len(self.vlans) > 0:
            vlan = self.vlans[0]
            logger.info("Using vlan %s" % str(vlan))
        return vlan
