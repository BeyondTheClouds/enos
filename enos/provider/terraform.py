from .host import Host
from ipaddress import IPv4Network
from jinja2 import Environment, FileSystemLoader
from provider import Provider
from ..utils.constants import TEMPLATE_DIR
from ..utils.extra import build_resources, expand_topology, build_roles
from ..utils.provider import load_config

import ipaddress
import json
import logging
import os
import subprocess

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

PROVIDER_CONFIG = {
    # NOTE(msimonin): we default to chameleon specific options
    # for the sake of illustration
    'type': 'terraform',
    'backend': 'openstack',
    'image_name': 'CC-Ubuntu16.04',
    'key_pair': 'enos-matt',
    'user': 'cc',
    'subnet_cidr': '10.87.23.0/24',
    'subnet_dns_nameservers': ['129.114.97.1', '129.114.97.2', '129.116.84.203'],
    'gateway': True,
    # NOTE(msimonin): Having to hardcode the device here is cumbersome
    'device': 'ens3'
}


def run(command):
    """Util function to run and display the stdout of a command"""
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = []
    while True:
        line = p.stdout.readline()
        stdout.append(line)
        print line,
        if line == '' and p.poll() is not None:
            break
    output = ''.join(stdout)
    exit = p.returncode
    err = '\n'.join(p.stderr.readlines())
    if exit != 0:
        logging.error(err)
        raise Exception("Error when running : %s" % command)
    return output, exit, err


class Terraform(Provider):
    def init(self, config, calldir, force_deploy=False):
        conf = load_config(config, default_provider_config=PROVIDER_CONFIG)
        provider_config = conf['provider']
        backend = conf['provider']['backend']
        machines = {}

        # NOTE(msimonin): we use the user_data script to create an additional
        # veth pair.
        user_data = os.path.join(CURRENT_DIR, "%s.sh" % backend)
        for size, roles in conf['resources'].items():
            for role, nb in roles.items():
                machines.setdefault(size, {
                    'count': 0,
                    'key_pair': conf['provider']['key_pair'],
                    'image': conf['provider']['image_name'],
                    'flavor_name': size,
                    'resource_name': 'enos-%s' % (size.replace('.', '_')),
                    'name': 'enos-%s' % size,
                    'user_data': user_data
                })
                machines[size]['count'] = machines[size]['count'] + nb

        loader = FileSystemLoader(searchpath=TEMPLATE_DIR)
        env = Environment(loader=loader)
        template = env.get_template("terraform-%s.tf.j2" % backend)

        tfile = template.render(machines=machines, provider_config=provider_config)
        tfile_path = os.path.join(calldir, "terraform-%s.tf" % backend)
        with open(tfile_path, 'w') as f:
            f.write(tfile)

        run("terraform validate")
        if force_deploy:
            run("terraform destroy")

        run('terraform apply')
        # NOTE(msimonin): we could maybe iterate here on plan/apply
        # until all the resources are up or a max retry is reached
        (out, exit, err) = run('terraform output --json')
        output = json.loads(out)
        logging.info("terraform returns with %s" % output)
        hosts = []
        extra = {'ansible_become': 'yes'}
        if 'gateway' in output:
            gateway = output['gateway']['value']
            gateway_user = conf['provider'].get('gateway_user', conf['provider'].get('user'))
            extra.update({
                'gateway': gateway,
                'gateway_user': gateway_user,
                'forward_agent': True
                })

        for k, v in output.items():
            key = k.split('-')[0]
            if key == 'ips':
                hosts.extend(
                        map(
                            lambda v: Host(
                                v[1],
                                alias=v[0],
                                user=conf['provider'].get('user'),
                                extra=extra), v["value"].items()))

        roles = build_roles(
                conf,
                hosts,
                lambda n: n.alias.split('-')[1])

        logging.info(roles)

        # NOTE(msimonin): if we provision several networks, we'll need to pick
        # ips from a created subnet not from the existing one from the existing
        # one
        out_net = output['subnet']['value']
        net = ipaddress.ip_network(out_net['cidr'])
        network = {
            'cidr': out_net['cidr'],
            'start': str(net[100]),
            'end': str(net[-3]),
            'gateway': out_net['gateway_ip'],
            'dns': '8.8.8.8'
        }

        return (roles, network, (conf['provider']['device'], 'veth0'))

    def destroy(self, calldir, env):
        run("terraform destroy -force")
