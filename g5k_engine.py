import pprint, os, sys
pp = pprint.PrettyPrinter(indent=4).pprint
import json

import execo as EX
from string import Template
from execo import configuration
from execo.log import style
import execo_g5k as EX5
from execo_g5k.api_utils import get_cluster_site
from execo_engine import Engine, logger

# Shortcut
funk = EX5.planning

# Default values
DEFAULT_JOB_NAME = 'FUNK'

MAX_ATTEMPTS = 5

class G5kEngine(Engine):
	def __init__(self):
		"""Initialize the Execo Engine"""
		super(G5kEngine, self).__init__()

		# Add some command line arguments
		self.options_parser.add_option("-f", dest="config_path",
			help="Path to the JSON file describing the Grid'5000 deployment and the deployment.")

	def load(self):
		"""Load the JSON configuration file"""

		if self.options.config_path is None:
			logger.error("You must specify a configuration file with '-f'")
			sys.exit(22)

		# Load the configuration file
		try:
			with open(self.options.config_path) as config_file:
				self.config = json.load(config_file)
		except:
			logger.error("Error reading configuration file %s" % self.options.config_path)
			t, value, tb = sys.exc_info()
			print("%s %s" % (str(t), str(value)))
			sys.exit(23)

		if 'job_name' not in self.config:
			self.config['job_name'] = DEFAULT_JOB_NAME

		if 'reservation' not in self.config:
			self.config['reservation'] = None

		# Nothing is excluded by default
		if 'excluded_elements' not in self.config:
			self.config['excluded_elements'] = []

		# Count the number of nodes we are requesting
		self.total_nodes = 0
		for cluster in self.config['resources']:
			if isinstance(self.config['resources'][cluster], int):
				self.total_nodes += self.config['resources'][cluster]
			else:
				print("Invalid number of nodes: %s" % self.config['resources'][cluster])
				sys.exit(24)
	
	def get_job(self):
		"""Get the hosts from an existing job (if any) or from a new job.
		This will perform a reservation if necessary."""

		# Look if there is a running job
		self.gridjob, _ = funk.get_job_by_name(self.config['job_name'])

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

		self.start_date = None
		job_info = EX5.get_oargrid_job_info(self.gridjob)
		if 'start_date' in job_info:
			self.start_date = ['start_date']

		self.subnets = None

		return self.gridjob
	
	def _make_reservation(self):
		"""Make a new reservation."""
		
		logger.info('Finding slot for the job...')
		elements = self.config['resources']
		
		# Do we want subnets?
		if 'subnets' in self.config:
			elements['subnets'] = self._subnet_to_string(self.config['subnets'])

		planning = funk.get_planning(elements.keys(),
				starttime=self.config['reservation'])
		slots = funk.compute_slots(planning,
				walltime=self.config['walltime'].encode('ascii', 'ignore'),
				excluded_elements=self.config['excluded_elements'])

		startdate, enddate, resources = funk.find_free_slot(slots, elements)
		resources = funk.distribute_hosts(resources, elements,
				self.config['excluded_elements'])

		if startdate is None:
			logger.error('Could not find a slot for the requested resources.')
			sys.exit(25)

		jobs_specs = funk.get_jobs_specs(resources, name=self.config['job_name'],
				excluded_elements=self.config['excluded_elements'])

		for job, frontend in jobs_specs:
			if frontend in self.config['subnets']:
				job.resources = self.config['subnets'][frontend] + \
					'+' + job.resources

		logger.info(jobs_specs)
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
	
	def delete_job(self):
		EX5.oardel([self.gridjob])
	
	def _subnet_to_string(self, subnet):
		tmp = map(lambda res: "%s:%s" % (res[0], res[1]), subnet.items())
		return reduce(lambda a, b: "%s,%s" % (a, b), tmp)

