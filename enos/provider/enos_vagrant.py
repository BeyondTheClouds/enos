from .host import Host
from ipaddress import IPv4Network
from jinja2 import Environment, FileSystemLoader
from provider import Provider
from ..utils.constants import TEMPLATE_DIR
from ..utils.extra import build_resources, expand_topology, build_roles

import logging
import os
import vagrant

SIZES = {
    'tiny': {
        'cpu': 1,
        'mem': 512
    },
    'small': {
        'cpu': 1,
        'mem': 1024
    },
    'medium': {
        'cpu': 2,
        'mem': 2048
    },
    'big': {
        'cpu': 3,
        'mem': 3072,
    },
    'large': {
        'cpu': 4,
        'mem': 4096
    },
    'extra-large': {
        'cpu': 6,
        'mem': 6144
    }
}


class Enos_vagrant(Provider):
    def init(self, config, calldir, force_deploy=False):
        """python -m enos.enos up
        Read the resources in the configuration files.  Resource claims must be
        grouped by sizes according to the predefined SIZES map.
        """
        self.config = config
        if 'topology' in self.config:
            # expand the groups first
            self.config['topology'] = expand_topology(self.config['topology'])
            # Build the ressource claim to g5k
            # We are here using a flat combination of the resource
            # resulting in (probably) deploying one single region
            self.config['resources'] = build_resources(self.config['topology'])

        net_pools = {
            'ip1': list(IPv4Network(u'192.168.142.0/25')),
            'ip2': list(IPv4Network(u'192.168.143.0/25')),
            'ip3': list(IPv4Network(u'192.168.144.0/25')),
        }

        # Build a list of machines that will be used to generate the
        # Vagrantfile
        machines = []
        for size, roles in self.config['resources'].items():
            for role, nb in roles.items():
                for i in range(nb):
                    ip1 = str(net_pools['ip1'].pop())
                    _, _, _, name = ip1.split('.')
                    machines.append({
                        'role': role,
                        # NOTE(matrohon): don't base the name of the VM on its
                        # role, build_roles will then set the final role of
                        # each VM
                        'name': "enos-%s" % name,
                        'size': size,
                        'cpu': SIZES[size]['cpu'],
                        'mem': SIZES[size]['mem'],
                        'ip1': ip1,
                        'ip2': str(net_pools['ip2'].pop()),
                        'ip3': str(net_pools['ip3'].pop()),
                        })
        loader = FileSystemLoader(searchpath=TEMPLATE_DIR)
        env = Environment(loader=loader)
        template = env.get_template('Vagrantfile.j2')

        vagrantfile = template.render(machines=machines)
        vagrantfile_path = os.path.join(calldir, "Vagrantfile")
        with open(vagrantfile_path, 'w') as f:
            f.write(vagrantfile)

        v = vagrant.Vagrant(root=calldir,
                            quiet_stdout=False,
                            quiet_stderr=False)
        if force_deploy:
            v.destroy()
        # NOTE(matrohon) : force no parallel provisionning since it fails with
        # libvrit/hostmanager plugins for vagrant
        v._call_vagrant_command(['up', '--no-parallel'])
        v.provision()
        # Distribute the machines according to the resource/topology
        # specifications
        r = build_roles(
                    self.config,
                    machines,
                    lambda m: m['size'])
        roles = {}

        for role, machines in r.items():
            roles.setdefault(role, [])
            for machine in machines:
                keyfile = v.keyfile(vm_name=machine['name'])
                port = v.port(vm_name=machine['name'])
                address = v.hostname(vm_name=machine['name'])
                user = v.user(vm_name=machine['name'])
                roles[role].append(Host(address,
                                        alias=machine['name'],
                                        user='root',
                                        port=port,
                                        keyfile=keyfile))
        logging.info(roles)
        network = {
                'cidr': '192.168.142.0/24',
                'start': str(net_pools['ip1'][3]),
                'end': str(net_pools['ip1'][-1]),
                'dns': '8.8.8.8',
                'gateway': '192.168.142.1'
        }
        network_interface = 'eth1'
        external_interface = 'eth2'
        return (roles, network, (network_interface, external_interface))

    def destroy(self, calldir, env):
        v = vagrant.Vagrant(root=calldir,
                            quiet_stdout=False,
                            quiet_stderr=True)
        v.destroy()
