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
import operator

# Default values
DEFAULT_CONF_FILE = 'reservation.yaml'

MAX_ATTEMPTS = 5

DEFAULT_CONN_PARAMS = {'user': 'root'}

DEFAULT_ROLES = {
    "controller": 0,
    "compute": 0,
    "network": 0,
    "storage": 0,
}

DEFAULT_CONFIG = {
    "name": "kolla-discovery",
    "walltime": "02:00:00",
    "env_name": 'ubuntu1404-x64-min',
    "reservation": None,
    "subnets": {}
}

class G5kEngine(Engine):
    def __init__(self):
        """Initialize the Execo Engine"""
        super(G5kEngine, self).__init__()

        # Add some command line arguments
        self.options_parser.add_option("-f", dest="config_path",
            help="Path to the configuration file describing the Grid'5000 the deployment.")

        self.options_parser.add_option("--force-deploy", dest="force_deploy",
            help="Force deployment",
            default=False,
            action="store_true")

    def load(self):
        """Load the configuration file"""
        if self.options.config_path is None:
            self.options.config_path = DEFAULT_CONF_FILE

        # Load the configuration file
        try:
            with open(self.options.config_path) as config_file:
                config = yaml.load(config_file)
        except:
            logger.error("Error reading configuration file %s" %
                         self.options.config_path)
            t, value, tb = sys.exc_info()
            print("%s %s" % (str(t), str(value)))
            sys.exit(23)

        self.config = {}
        self.config.update(DEFAULT_CONFIG)
        self.config.update(config)

        # We rebuild the resources to apply default values
        self.config["resources"] = {}
        for cluster, roles in config['resources'].items():
            self.config['resources'][cluster] = DEFAULT_ROLES.copy()
            self.config['resources'][cluster].update(roles)

        logger.info("Configuration file loaded : %s" % self.options.config_path)
        logger.info(pf(self.config))

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
            self.nodes = EX5.get_oargrid_job_nodes(self.gridjob)
            attempts += 1

        self.oarjobs = EX5.get_oargrid_job_oar_jobs(self.gridjob)

        # TODO - Start_date is never used, deadcode ? Ad_rien_ - August 11th 2016
        self.start_date = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'start_date' in job_info:
            self.start_date = job_info['start_date']

        self.user = None
        job_info = EX5.get_oargrid_job_info(self.gridjob)
        if 'user' in job_info:
            self.user = job_info['user']

        self.subnets = None

        return self.gridjob

    def deploy(self):
        # Deploy all the nodes
        logger.info("Deploying %s on %d nodes %s" %
            (self.config['env_name'], len(self.nodes),
             '(forced)' if self.options.force_deploy else ''))
        deployed, undeployed = EX5.deploy(
        EX5.Deployment(
            self.nodes,
            env_name=self.config['env_name']
        ), check_deployed_command=not self.options.force_deploy)

        # Check the deployment
        if len(undeployed) > 0:
            logger.error("%d nodes where not deployed correctly:" % len(undeployed))
            for n in undeployed:
                logger.error(style.emph(undeployed.address))

        logger.info("Nodes deployed: %s" % deployed)

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
                    self.nodes, lambda node: node.address.split('-')[0]):
                pools.setdefault(cluster, []).extend(list(nodes))

            return pools

        def pick_nodes(pool, n):
            "Picks n node in a pool of nodes."
            nodes = pool[:n]
            del pool[:n]
            return nodes

        # Maps a role (eg, controller) with a list of G5K node.
        roles = {}
        pools = mk_pools()
        for cluster, rs in self.config['resources'].items():
            for r, n in rs.items():
                roles.setdefault(r, []).extend(pick_nodes(pools[cluster], n))

        logger.info("Roles: %s" % pf(roles))
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
        # - Subnet per site (if any)
        for site, subnet in self.config["subnets"].items():
            criteria.setdefault(site, []).append(subnet)

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

        if gridjob is not None:
            self.gridjob = gridjob
            logger.info("Using new oargrid job %s" % style.emph(self.gridjob))
        else:
            logger.error("No oar job was created.")
            sys.exit(26)

    def get_subnets(self):
        if self.subnets is None:
            self.subnets = {}
            for job, site in self.oarjobs:
                self.subnets[site] = EX5.get_oar_job_subnets(job, site)
        return self.subnets

    def get_free_ip(self):
        subnet = self.get_subnets().values()[0]
        available_ips = map(lambda ip: ip[0], subnet[0])
        return available_ips.pop(0)

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
        script += "ssh -F /tmp/openstack_ssh_config -N -L " + `port` + ":" + internal_vip_address + ":80 " + self.user + "@access.grid5000.fr &\n"

        script += "echo 'http://localhost:8080'\n"
        logger.info(script)
        logger.info("___")

        with open(self.result_dir + "/dashboard_tunnels.sh", 'w') as f:
            f.write(script)

        logger.info("ssh tunnel informations:")
        logger.info("___")
