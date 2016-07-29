#! /usr/bin/env python

import sys, os, subprocess

from ansible.inventory import Inventory
import ansible.callbacks
import ansible.playbook

import jinja2
from execo.log import style
from execo_engine import logger
from engine.g5k_engine import G5kEngine

SYMLINK_NAME = 'current'

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
        
        deployed, undeployed = self.deploy()
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
        registry_node = self.nodes[0]

        # Generate the inventory file
        vars = {
            'all_nodes'          : self.nodes,
            'docker_registry_node'       : registry_node,
            'control_nodes'          : roles['controllers'],
            'network_nodes'          : roles['network'],
            'compute_nodes'          : roles['compute'],
            'storage_nodes'          : roles['storage'],
            'kolla_internal_vip_address' : internal_vip_address
        }

        inventory_path = os.path.join(self.result_dir, 'multinode')
        render_template('templates/multinode.jinja2', vars, inventory_path)
        logger.info("Inventory file written to " + style.emph(inventory_path))

        # TODO workarround
        self.exec_command_on_nodes(self.nodes, 'apt-get -y --force-yes install apt-transport-https',
            'Workarround: installing apt-transport-https...')

        # Install python on the nodes
        self.exec_command_on_nodes(self.nodes, 'apt-get update && apt-get -y install python',
            'Installing Python on all the nodes...')

        # Run the Ansible playbooks
        playbooks = ['site.yml']

        extra_vars = {
            'registry_hostname': registry_node.address,
        }

        run_ansible(playbooks, inventory_path, extra_vars)

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

        admin_openrc_path = os.path.join(self.result_dir, 'admin-openrc')
        logger.info("Generating the admin-openrc file to %s" % (admin_openrc_path))
        admin_openrc_vars = {
            'keystone_address': internal_vip_address
        }
        render_template('templates/admin-openrc.jinja2', admin_openrc_vars, admin_openrc_path)

        link = os.path.abspath(SYMLINK_NAME)
        if os.path.exists(link):
            os.remove(link)
        os.symlink(self.result_dir, link)

        logger.info("Symlinked %s to %s" % (self.result_dir, link))
        logger.info("You can now run ./02_deploy_kolla.sh or connect to horizon on %s:80" % roles['controllers'][0].address)

        sys.exit(0)


def run_ansible(playbooks, inventory_path, extra_vars):
        inventory = Inventory(inventory_path)

        for path in playbooks:
            logger.info("Running playbook %s with vars:\n%s" % (style.emph(path), extra_vars))
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

def render_template(template_path, vars, output_path):
    loader = jinja2.FileSystemLoader(searchpath='.')
    env = jinja2.Environment(loader=loader)
    template = env.get_template(template_path)
    
    rendered_text = template.render(vars)
    with open(output_path, 'w') as f:
        f.write(rendered_text)

if __name__ == "__main__":
    KollaG5k().start()
