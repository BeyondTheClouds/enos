# NOTE(msimonin): we should get rid of this
from ..utils.extra import (build_roles,
                           get_total_wanted_machines,
                           gen_resources)
from .host import Host
from glanceclient import client as glance
from keystoneauth1.identity import v2
from keystoneauth1 import session
from neutronclient.neutron import client as neutron
from novaclient import client as nova
from operator import itemgetter
from provider import Provider

import ipaddress
import logging
import os
import re
import time

PREFIX = 'enos'
CONFIGURE_NETWORK = True
NETWORK_NAME = "%s-network" % PREFIX
SUBNET_NAME = "%s-subnet" % PREFIX

# NOTE(msimonin): build the subnet following the good rules
# https://www.chameleoncloud.org/docs/bare-metal-user-guide/network-isolation-bare-metal/
# Some defaults
SUBNET_CIDR = '10.87.23.0/24'
ALLOCATION_POOL = {'start': '10.87.23.10', 'end': '10.87.23.100'}
DNS_NAMESERVERS = ['8.8.8.8', '8.8.4.4']

# These are private resources
ROUTER_NAME = "%s-router" % PREFIX
SECGROUP_NAME = "%s-secgroup" % PREFIX
GLANCE_VERSION = '2'
NEUTRON_VERSION = '2'
NOVA_VERSION = '2.1'

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def get_session():
    """Build the session object."""
    auth = v2.Password(
        auth_url=os.environ["OS_AUTH_URL"],
        username=os.environ["OS_USERNAME"],
        password=os.environ["OS_PASSWORD"],
        tenant_id=os.environ["OS_TENANT_ID"])
    return session.Session(auth=auth)


def check_glance(session, image_name):
    """Check that the base image is available.

    Fails if the base image isn't added.
    This means the image should be added manually.
    """
    gclient = glance.Client(GLANCE_VERSION, session=session)
    images = gclient.images.list()
    name_ids = map(lambda n: {'name': n['name'], 'id': n['id']}, images)
    if image_name not in map(itemgetter('name'), name_ids):
        logging.error("[glance]: Image %s is missing" % image_name)
        raise Exception("Image %s is missing" % image_name)
    else:
        image = [i for i in name_ids if i['name'] == image_name]
        image_id = image[0]['id']
        logging.info("[glance]: Using image %s:%s" % (image_name, image_id))
    return image_id


def check_flavors(session, resources):
    """Build the flavors mapping

    returns the mappings id <-> flavor
    """
    nclient = nova.Client(NOVA_VERSION, session=session)
    flavors = nclient.flavors.list()
    to_id = dict(map(lambda n: [n.name, n.id], flavors))
    to_flavor = dict(map(lambda n: [n.id, n.name], flavors))
    return to_id, to_flavor


def check_network(session, configure_network, network, subnet,
        dns_nameservers=None, allocation_pool=None):
    """Check the network status for the deployment.

    If needed, it creates a dedicated :
        * private network /subnet
        * router between this network and the external network
    """
    nclient = neutron.Client('2', session=session)

    # Check the security groups
    secgroups = nclient.list_security_groups()['security_groups']
    secgroup_name = SECGROUP_NAME
    if secgroup_name not in map(itemgetter('name'), secgroups):
        secgroup = {'name': secgroup_name,
                    'description': 'Enos Security Group'}
        res = nclient.create_security_group({'security_group': secgroup})
        secgroup = res['security_group']
        logging.info("[neutron]: %s security group created" % secgroup_name)
        # create the rules
        tcp = {'protocol': 'tcp',
               'direction': 'ingress',
               'port_range_min': '1',
               'port_range_max': '65535',
               'security_group_id': secgroup['id']}
        icmp = {'protocol': 'icmp',
                'direction': 'ingress',
                'security_group_id': secgroup['id']}
        nclient.create_security_group_rule({'security_group_rule': tcp})
        logging.info("[neutron]: %s rule (all tcp) created" % secgroup_name)
        nclient.create_security_group_rule({'security_group_rule': icmp})
        logging.info("[neutron]: %s rule (all icmp) created" % secgroup_name)
    else:
        logging.info("[neutron]: Reusing security-groups %s " % secgroup_name)

    networks = nclient.list_networks()['networks']
    network_name = network['name']
    if network_name not in map(itemgetter('name'), networks):
        network = {'name': network_name}
        res = nclient.create_network({'network': network})
        network = res['network']
        logging.info("[neutron]: %s network created" % network_name)
    else:
        network = [n for n in networks if n['name'] == network_name][0]
        logging.info("[neutron]: Reusing existing %s network", network)

    # find ext_net
    ext_net = [n for n in networks if n['router:external']]
    if len(ext_net) < 1:
        raise Exception("No external network found")
    ext_net = ext_net[0]

    subnets = nclient.list_subnets()['subnets']
    subnet_name = subnet['name']
    if (subnet_name not in map(itemgetter('name'), subnets) and
            configure_network):
        subnet = {'name': subnet['name'],
        'network_id': network['id'],
        # NOTE(msimonin): using the dns of chameleon
        # for a generic openstack provider we should think to
        # parameteried this or use public available dns
        'cidr': subnet['cidr'],
        'ip_version': 4}
        if dns_nameservers is not None:
            subnet.update({'dns_nameservers': dns_nameservers})
        if allocation_pool is not None:
            subnet.update({'allocation_pools': [allocation_pool]})

        s = nclient.create_subnet({'subnet': subnet})
        logging.debug(s)
        subnet = s['subnet']
        logging.info("[neutron]: %s subnet created" % subnet_name)
    else:
        subnet = [s for s in subnets if s['name'] == subnet_name][0]
        logging.info("[neutron]: Reusing %s subnet", subnet)

    # create a router
    routers = nclient.list_routers()
    router_name = ROUTER_NAME
    logging.debug(routers)
    if (router_name not in map(itemgetter('name'), routers['routers']) and
            configure_network):
        router = {
            'name': router_name,
            'external_gateway_info': {
                'network_id': ext_net['id']
            }
        }
        r = nclient.create_router({'router': router})
        logging.info("[neutron]  %s router created" % router_name)
        # NOTE(msimonin): We should check the interface outside this block
        # in case the router is created but the interface is not added
        interface = {
            'subnet_id': subnet['id'].encode('UTF-8')
        }
        nclient.add_interface_router(r['router']['id'], interface)

    return (ext_net, network, subnet)


def get_free_floating_ip(env):
    nclient = neutron.Client('2', session=env['session'])
    fips = nclient.list_floatingips()['floatingips']
    fips = filter(lambda fip: fip['fixed_ip_address'] is None, fips)
    if len(fips) > 0:
        fip = fips.pop()
    else:
        # create from scratch
        floatingip = {'floating_network_id': env['ext_net']['id']}
        fip = nclient.create_floatingip({'floatingip': floatingip})
        fip = fip['floatingip']
    logging.info("[neutron]: Using floating ip: %s", fip)
    return fip


def wait_for_servers(session, servers):
    """Wait for the servers to be ready.

    Note(msimonin): we don't garantee the SSH connection to be ready.
    """
    nclient = nova.Client(NOVA_VERSION, session=session)
    while True:
        deployed = []
        undeployed = []
        for server in servers:
            c = nclient.servers.get(server.id)
            if c.addresses != {} and c.status == 'ACTIVE':
                deployed.append(server)
            if c.status == 'ERROR':
                undeployed.append(server)
        logging.info("[nova]: Polling the Deployment")
        logging.info("[nova]: %s deployed servers" % len(deployed))
        logging.info("[nova]: %s undeployed servers" % len(undeployed))
        if len(deployed) + len(undeployed) >= len(servers):
            break
        time.sleep(3)
    return deployed, undeployed


def check_servers(session, resources, extra_prefix="",
        force_deploy=False, key_name=None, image_id=None,
        flavors='m1.medium', network=None, ext_net=None, scheduler_hints={}):
    """Checks the servers status for the deployment.

    If needed, it creates new servers and add a floating ip to one of them.
    This server can be used as a gateway to the others.
    """
    nclient = nova.Client(NOVA_VERSION, session=session)
    servers = nclient.servers.list(
        search_opts={'name': '-'.join([PREFIX, extra_prefix])})
    wanted = get_total_wanted_machines(resources)
    if force_deploy:
        for server in servers:
            server.delete()
        servers = []

    if len(servers) == wanted:
        logging.info("[nova]: Reusing existing servers : %s", servers)
        return servers
    elif len(servers) > 0 and len(servers) < wanted:
        raise Exception("Only %s/%s servers found" % (servers, wanted))

    # starting the servers
    total = 0
    for size, role, number in gen_resources(resources):
        logging.info("[nova]: Starting %s servers" % number)
        logging.info("[nova]: for role %s" % role)
        logging.info("[nova]: with extra hints %s" % scheduler_hints)
        for n in range(number):
            if type(flavors) == str:
                flavor = flavors
            else:
                flavor_to_id, id_to_flavor = flavors
                flavor = flavor_to_id[size]
            with open(os.path.join(CURRENT_DIR, 'openstack.sh'), 'r') as u:
                servers.append(nclient.servers.create(
                    name='-'.join([PREFIX, extra_prefix, str(total)]),
                    image=image_id,
                    flavor=flavor,
                    nics=[{'net-id': network['id']}],
                    key_name=key_name,
                    security_groups=[SECGROUP_NAME],
                    scheduler_hints=scheduler_hints,
                    userdata=u))
            total = total + 1
    return servers


def check_gateway(env, with_gateway, servers):
    gateway = sorted(servers, key=lambda s: s.id)[0]
    if with_gateway:
        nclient = nova.Client(NOVA_VERSION, session=env['session'])
        gateway = nclient.servers.get(gateway.id)
        gw_floating_ips = filter(
            lambda n: n['OS-EXT-IPS:type'] == 'floating',
            gateway.addresses[env['network']['name']])
        if len(gw_floating_ips) == 0:
            fip = get_free_floating_ip(env)
            gateway.add_floating_ip(fip['floating_ip_address'])
            gateway = nclient.servers.get(gateway.id)
        # else gateway already has an fip
        logging.info("[nova]: Reusing %s as gateway" % gateway)
    return gateway


def is_in_current_deployment(server, extra_prefix=""):
    """Check if an existing server in the system take part to
    the current deployment
    """
    return re.match(r"^%s" % '-'.join([PREFIX, extra_prefix]),
            server.name) is not None


def allow_address_pairs(session, network, subnet):
    """Allow several interfaces to be added and accessed from the other machines.

    This is particularly useful when working with virtual ips.
    """
    nclient = neutron.Client('2', session=session)
    ports = nclient.list_ports()
    ports_to_update = filter(
        lambda p: p['network_id'] == network['id'],
        ports['ports'])
    logging.info('[nova]: Allowing address pairs for ports %s' %
            map(lambda p: p['fixed_ips'], ports_to_update))
    for port in ports_to_update:
        try:
            nclient.update_port(port['id'], {
                'port': {
                    'allowed_address_pairs': [{
                        'ip_address': subnet
                        }]
                    }
                })
        except:
            # NOTE(msimonin): dhcp and router interface port
            # seems to have enabled_sec_groups = False which
            # prevent them to be updated, just throw a warning
            # a skip them
            logging.warn("Can't update port %s" % port)


def check_environment(conf):
    """Check all ressources needed by Enos."""
    session = get_session()
    image_id = check_glance(session, conf['provider'].get('image_name'))
    flavor_to_id, id_to_flavor = check_flavors(session, conf['resources'])
    ext_net, network, subnet = check_network(session,
        conf['provider']['configure_network'],
        conf['provider']['network'],
        subnet=conf['provider']['subnet'],
        dns_nameservers=conf['provider']['dns_nameservers'],
        allocation_pool=conf['provider']['allocation_pool'])

    return {
        'session': session,
        'image_id': image_id,
        'flavor_to_id': flavor_to_id,
        'id_to_flavor': id_to_flavor,
        'ext_net': ext_net,
        'network': network,
        'subnet': subnet
    }


def finalize(conf, env, servers, gateway, groupby, extra_ips=[]):
    # Distribute the machines according to the resource/topology
    # specifications
    r = build_roles(conf,
                    servers,
                    groupby)
    roles = {}
    extra = {}
    network_name = conf['provider']['network']['name']
    if conf['provider']['gateway']:
        gw_floating_ip = filter(
            lambda n: n['OS-EXT-IPS:type'] == 'floating',
            gateway.addresses[network_name])[0]['addr']
        user = conf['provider'].get('user')
        gw_user = conf['provider'].get('gateway_user', user)
        extra.update({
            'gateway': gw_floating_ip,
            'gateway_user': gw_user,
            'forward_agent': True
            })
    extra.update({'ansible_become': 'yes'})

    # ensuring that we inspect server in the same order
    servers = sorted(servers, key=lambda s: s.id)
    for role, servers in r.items():
        roles.setdefault(role, [])
        for idx, server in enumerate(servers):
            roles[role].append(Host(
                server.addresses[network_name][0]['addr'],
                # NOTE(msimonin): the alias is used by ansible and thus
                # must be an ascii hostname
                alias=str(server.name),
                user=conf['provider'].get('user'),
                extra=extra))

    net = ipaddress.ip_network(env['subnet']['cidr'])
    network = {
        'cidr': env['subnet']["cidr"],
        'start': str(net[100]),
        'end': str(net[-3]),
        'extra_ips': extra_ips,
        'gateway': env['subnet']["gateway_ip"],
        'dns': '8.8.8.8'
    }
    return (roles, network, (conf['provider']['network_interface'], 'veth0'))


class Openstack(Provider):
    def init(self, conf, force_deploy=False):
        """python -m enos.enos up
        Read the resources in the configuration files.  Resource claims must be
        grouped by sizes according to the predefined SIZES map.
        """
        env = check_environment(conf)
        servers = check_servers(
            env['session'],
            conf['resources'],
            force_deploy=force_deploy,
            key_name=conf['provider'].get('key_name'),
            image_id=env['image_id'],
            flavors=(env['flavor_to_id'], env['id_to_flavor']),
            network=env['network'],
            ext_net=env['ext_net'])

        deployed, undeployed = wait_for_servers(env['session'], servers)

        gateway = check_gateway(
            env,
            conf['provider'].get('gateway', False),
            deployed
            )

        allow_address_pairs(env['session'],
            env['network'],
            conf['provider']['subnet']['cidr'])

        # NOTE(msimonin): polling is missing for now
        # we aren't sure that machines are ssh-reachable
        return finalize(
            conf,
            env,
            deployed,
            gateway,
            lambda s: env['id_to_flavor'][s.flavor['id']])

    def default_config(self):
        return {
            'configure_network': CONFIGURE_NETWORK,
            'network': {'name': NETWORK_NAME},
            'subnet': {'name': SUBNET_NAME, 'cidr': SUBNET_CIDR},
            'dns_nameservers': DNS_NAMESERVERS,
            'allocation_pool': ALLOCATION_POOL,
            'gateway': True,

            # Mandatory keys
            'key_name': None,
            'image_name': None,
            'user': None
        }

    def destroy(self, env):
        session = get_session()
        nclient = nova.Client(NOVA_VERSION, session=session)
        servers = nclient.servers.list()
        for server in servers:
            if is_in_current_deployment(server):
                logging.info("Deleting %s" % server)
                server.delete()
