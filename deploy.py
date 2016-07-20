#! /usr/bin/env python

import sys, os

import jinja2
import execo as EX
import execo_g5k as EX5
from execo_engine import logger
from g5k_engine import G5kEngine

DEFAULT_CONN_PARAMS = {'user': 'root'}
ENV_NAME = 'ubuntu-x64-1404'

class KollaG5k(G5kEngine):
	def __init__(self):
		"""Just add a couple command line arguments"""
		super(KollaG5k, self).__init__()

		self.options_parser.add_option("--force-deploy", dest="force_deploy",
			help="Force deployment",
			default=False,
			action="store_true")

	def run(self):
		self.load()

		# Check we wil have enough nodes
		n_resources = reduce(lambda a, b: int(a) + int(b), self.config['resources'].values())
		n_services = reduce(lambda a, b: int(a) + int(b), self.config['openstack'].values())
		if n_resources < n_services:
			logger.error("The requested OpenStack services require %d nodes, but your job specification only includes %d" % (n_services, n_resources))
			sys.exit(32)

		self.get_job()
		
		# Deploy all the nodes
		logger.info("Deploying %s on %d nodes %s" %
			(ENV_NAME, len(self.nodes), '(forced)' if self.options.force_deploy else ''))
		deployed, undeployed = EX5.deploy(
			EX5.Deployment(
				self.nodes,
				env_name=ENV_NAME
			),
			check_deployed_command=not self.options.force_deploy
		)

		# Check the deployment
		if len(undeployed) > 0:
			logger.error("%d nodes where not deployed correctly:" % len(undeployed))
			for n in undeployed:
				logger.error(style.emph(undeployed.address))
			sys.exit(31)

		logger.info("Nodes deployed: %s" % deployed)

		# Distributed the nodes into roles
		roles = {}
		i = 0
		for role in self.config['openstack']:
			n = int(self.config['openstack'][role])
			roles[role] = map(lambda n: n.address, self.nodes[i:i+n])
			i += n

		logger.info("Roles: %s" % roles)

		# Generate Kolla's configuration file
		subnet = self.get_subnets().values()[0]
		ip = subnet[0][0][0]
		vars = {
			'kolla_internal_vip_address': ip
		}
		globals_path = os.path.join(self.result_dir, 'globals.yml')
		render_template('templates/globals.yml.jinja2', vars, globals_path)

		# Generate the inventory file
		vars = {
			'control_nodes':		'\n'.join(roles['controllers']),
			'network_nodes':		'\n'.join(roles['network']),
			'compute_nodes':		'\n'.join(roles['compute']),
			'storage_nodes':		'\n'.join(roles['storage'])
		}
		inventory_path = os.path.join(self.result_dir, 'mulitnode')
		render_template('templates/multinode.jinja2', vars, inventory_path)
		logger.info("Inventory file written to " + inventory_path)

		sys.exit(0)

		commands = [
			# Installing the requirements
			('apt-get update', 'Updating packages...'),
			('apt-get -y install python-pip git libffi-dev libssl-dev python-dev curl', 'Installing Kolla dependencies...'),
			('DEBIAN_FRONTEND=noninteractive apt-get -y install linux-image-generic-lts-wily', 'Installing new Linux Kernel...'),
			# Installing Docker
			('docker -v || curl -sSL https://get.docker.io | bash', 'Installing Docker...'),
			('mkdir -p /etc/systemd/system/docker.service.d', 'Setting up Docker...'),
			# Installing Kolla
			('mount --make-shared /run', 'Mounting /run...'),
			('pip install -U docker-py', 'Installing docker-py...'),
			('pip install -U ansible==1.9.4', 'Installing ansible...'),
			('test -d kolla || git clone -b stable/mitaka https://git.openstack.org/openstack/kolla', 'Cloning Kolla...'),
			('pip install kolla/', 'Installing Kolla...'),
			('cp -r kolla/etc/kolla /etc/', 'Copying into /etc/kolla...')
		]

		for c in commands:
			exec_command_on_nodes(self.nodes, c[0], c[1])


		# Sending globals.yml
		logger.info("Sending /etc/kolla/globals.yml to all nodes...")
		EX.Put(self.nodes, [globals_yml_path], '/etc/kolla/').run()

		# Deploying Kolla
		master = self.nodes[1]
		exec_command_on_nodes(master, 'kolla-genpwd', 'Generating Kolla passwords...')
		exec_command_on_nodes(master, 'kolla-ansible precheck', 'Running prechecks...')
		exec_command_on_nodes(master, 'kolla-ansible pull -vvv', 'Pulling containers...')
		exec_command_on_nodes(master, 'kolla-ansible deploy -vvv', 'Deploying kolla-ansible...')


def exec_command_on_nodes(nodes, cmd, label, conn_params=None):
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

def render_template(template_path, vars, output_path):
	loader = jinja2.FileSystemLoader(searchpath='.')
	env = jinja2.Environment(loader=loader)
	template = env.get_template(template_path)
	
	rendered_text = template.render(vars)
	with open(output_path, 'w') as f:
		f.write(rendered_text)

if __name__ == "__main__":
	KollaG5k().start()
