#! /usr/bin/env python

import sys, os, subprocess

from ansible.inventory import Inventory
import ansible.callbacks
import ansible.playbook

import jinja2
import execo as EX
from execo.log import style
import execo_g5k as EX5
from execo_engine import logger
from g5k_engine import G5kEngine

DEFAULT_CONN_PARAMS = {'user': 'root'}
ENV_NAME = 'ubuntu-x64-1404'
KOLLA_REPO = 'https://git.openstack.org/openstack/kolla'
KOLLA_BRANCH = 'stable/mitaka'

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
			roles[role] = self.nodes[i:i+n]
			i += n

		logger.info("Roles: %s" % roles)

		# Get an IP for 'Kolla internal vip address'
		subnet = self.get_subnets().values()[0]
		available_ips = map(lambda ip: ip[0], subnet[0])
		internal_vip_address = available_ips.pop(0)

		# These will be the Docker registries
		registry_nodes = [self.nodes[0]]

		# Generate the inventory file
		vars = {
			'all_nodes':					self.nodes,
			'docker_registry_nodes':	registry_nodes,
			'control_nodes':				roles['controllers'],
			'network_nodes':				roles['network'],
			'compute_nodes':				roles['compute'],
			'storage_nodes':				roles['storage'],
			'kolla_internal_vip_address': internal_vip_address
		}

		inventory_path = os.path.join(self.result_dir, 'multinode')
		render_template('templates/multinode.jinja2', vars, inventory_path)
		logger.info("Inventory file written to " + inventory_path)

		# Install python on the nodes
		exec_command_on_nodes(self.nodes, 'apt-get update && apt-get -y install python',
			'Installing Python on all the nodes...')

		# Clone or pull Kolla
		if os.path.isdir('kolla'):
			logger.info("Pulling Kolla...")
			os.system("cd kolla; git pull > /dev/null")
		else:
			logger.info("Cloning Kolla...")
			os.system("git clone %s -b %s > /dev/null" % (KOLLA_REPO, KOLLA_BRANCH))

		# Generating Ansible globals.yml
		globals_path = os.path.join(self.result_dir, 'globals.yml')
		render_template('templates/globals.yml.jinja2', vars, globals_path)
		logger.info("Wrote " + style.emph(globals_path))
		os.system("cp templates/passwords.yml %s/" % self.result_dir)

		# Run the Ansible playbooks
		playbooks = [
			'ansible/setup_hosts.yml',
			'ansible/docker_registry.yml'
		]

		extra_vars = {
			'kolla_internal_vip_address': internal_vip_address,
			'kolla_external_vip_address':	'',
			'network_interface':				'',
			'node_config_directory':		'',
			'enable_ceph':						''
		}

		run_ansible(playbooks, inventory_path, extra_vars)

		# Deploying OpenStack with Kolla
		if not run_kolla(inventory_path, self.result_dir, 'pull'):
			sys.exit(10)
	
		if not run_kolla(inventory_path, self.result_dir, 'deploy'):
			sys.exit(11)

		if not run_kolla(inventory_path, self.result_dir, 'post-deploy'):
			sys.exit(12)
	


def run_kolla(inventory_path, config_path, action):
	kolla_args = ['-i', inventory_path, '--configdir', config_path]
	cmd = ['kolla/tools/kolla-ansible', action] + kolla_args

	logger.info("Running %s" % style.emph(' '.join(cmd)))

	try:
		p = subprocess.Popen(cmd)
		p.communicate()
		p.wait()

		if p.returncode != 0:
			logger.error("kolla-ansible returned a non-zero code: %d" % p.returncode)
	except KeyboardInterrupt:
		sys.exit(1)

	return p.returncode == 0


def run_ansible(playbooks, inventory_path, extra_vars):
		inventory = Inventory(inventory_path)

		for path in playbooks:
			logger.info("Running playbook: " + style.emph(path))
			stats = ansible.callbacks.AggregateStats()
			playbook_cb = ansible.callbacks.PlaybookCallbacks(verbose=1)

			pb = ansible.playbook.PlayBook(
				playbook=path,
				inventory=inventory,
				extra_vars=extra_vars,
				stats=stats,
				callbacks=playbook_cb,
				runner_callbacks=ansible.callbacks.PlaybookRunnerCallbacks(stats, verbose=1),
				forks=10
			)

			pb.run()
			
			hosts = pb.stats.processed.keys()
			failed_hosts = []
			unreachable_hosts = []
			
			for h in hosts:
				t = pb.stats.summarize(h)
				if t['failures'] > 0:
					failed_hosts.append(h)
					
				if t['unreachable'] > 0:
					unreachable_hosts.append(h)
				
			if len(failed_hosts) > 0:
				logger.error("Failed hosts: %s" % failed_hosts)
			if len(unreachable_hosts) > 0:
				logger.error("Unreachable hosts: %s" % unreachable_hosts)

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
