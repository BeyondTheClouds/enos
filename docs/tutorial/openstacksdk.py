#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

import openstack


logging.basicConfig(level=logging.INFO)
LOG   = logging.getLogger(__name__)


def make_cloud():
    """Connects to OpenStack cloud using environment variables

    Returns:
        An new openstack.connection.Connection

    Refs:
        - https://docs.openstack.org/openstacksdk/latest/user/connection.html
    """
    LOG.info("New admin authentication on %s" % os.environ['OS_AUTH_URL'])
    return openstack.connect(cloud='envvars')


def make_account(identity, users):
    """Create a new project an put `users` in it.

    Create a new project if it doesn't exists and put
    users `users` in it. Then assigne member and heat roles
    to these users in the newly created project.

    Args:
        identity: Proxy for identity aka keystone [1]
        users: A list of users name to create and put into the project,
            users can access OpenStack with the password "demo".

    Returns:
        The newly created project [2]

    Refs:
        [1] https://docs.openstack.org/openstacksdk/latest/user/proxies/identity_v3.html
        [2] https://docs.openstack.org/openstacksdk/latest/user/resources/identity/v3/project.html#openstack.identity.v3.project.Project
    """
    # Compute project name from users name
    project_name = "project-%s" % '-'.join(u for u in users)

    # Test if the project exists and create it if need be
    project = identity.find_project(project_name)
    if not project:
        project = identity.create_project(
            name=project_name,
            description="Project of %s." % ', '.join(u for u in users))
        LOG.info("Created a new project %s" % project)

    for user_name in users:
        # Test if user exists and create it if need be
        user = identity.find_user(user_name)
        if not user:
            user = identity.create_user(
                name=user_name, password="demo")
        LOG.info("Created a new user %s with password demo" % user)

        # Assign user to member and heat_stack_owner role in newly
        # created project.
        for r in ["member", "heat_stack_owner"]:
            role = identity.find_role(r)

            # The `heat_stack_owner` role only exists if heat is deployed
            if role:
                identity.assign_project_role_to_user(project, user, role)
                LOG.info("Assigne role %s to user %s in project %s"
                        % (role, user, project))

    return project


def make_private_net(net, project):
    """Create a new private network only visible by members of `project`.

    Args:
        net: Proxy for network aka neutron [1]
        project: An OpenStack project [2]

    Returns:
        The subnet of the newly created private network [3]

    Refs:
        [1] https://docs.openstack.org/openstacksdk/latest/user/proxies/network.html
        [2] https://docs.openstack.org/openstacksdk/latest/user/resources/identity/v3/project.html#openstack.identity.v3.project.Project
        [3] https://docs.openstack.org/openstacksdk/latest/user/resources/network/v2/subnet.html#openstack.network.v2.subnet.Subnet
    """
    # Test if the private network exists and create it if need be
    # https://docs.openstack.org/openstacksdk/latest/user/resources/network/v2/network.html#openstack.network.v2.network.Network
    private_net = net.find_network("private", project_id=project.id)
    if not private_net:
        private_net = net.create_network(
            name="private",
            project_id=project.id,
            provider_network_type="vxlan")
        LOG.info("Created a new private network %s" % private_net)

    # Test if the subntet exists and create it if need be
    # https://docs.openstack.org/openstacksdk/latest/user/resources/network/v2/subnet.html#openstack.network.v2.subnet.Subnet
    private_snet = net.find_subnet("private-subnet", network_id=private_net.id)
    if not private_snet:
        private_snet = net.create_subnet(
            name="private-subnet",
            network_id=private_net.id,
            project_id=project.id,
            ip_version=4,
            is_dhcp_enable=True,
            cidr="10.0.0.0/24",
            gateway_ip="10.0.0.1",
            allocation_pools=[{"start": "10.0.0.2", "end": "10.0.0.254"}],
            # dns.watch
            dns_nameservers=["84.200.69.80", "84.200.70.40"])
        LOG.info("Created a new private subnet %s" % private_snet)

    return private_snet


def make_router(net, project, priv_snet):
    """Make a router for communications between private and public net.

    Enos comes with a public network setup in a KaVLAN. This function
    makes a router between the public network and a `priv_sunet`.
    Args:
        net: Proxy for network aka neutron [1]
        project: An OpenStack project [2]
        priv_snet: The subnet of private network to put in the router [3]

    Refs:
        [1] https://docs.openstack.org/openstacksdk/latest/user/proxies/network.html
        [2] https://docs.openstack.org/openstacksdk/latest/user/resources/identity/v3/project.html#openstack.identity.v3.project.Project
        [3] https://docs.openstack.org/openstacksdk/latest/user/resources/network/v2/subnet.html#openstack.network.v2.subnet.Subnet
    """
    # Get the public net from Enos
    public_net  = net.find_network("public", ignore_missing=False)
    public_snet = net.find_subnet("public-subnet", ignore_missing=False)

    # Test if the router exists and create it if need be
    # https://docs.openstack.org/openstacksdk/latest/user/resources/network/v2/router.html#openstack.network.v2.router.Router
    router = net.find_router("router", project_id=project.id)
    if not router:
        router = net.create_router(
            name="router",
            project_id=project.id,
            # Add public gateway
            external_gateway_info={
                'network_id': public_net.id,
                'enable_snat': True,
                'external_fixed_ips': [{'subnet_id': public_snet.id,}]
            })
        LOG.info("Created a new router %s" % router)

        # Add private interface
        res = net.add_interface_to_router(router, subnet_id=priv_snet.id)
        LOG.info("Added private interface %s to router" % res)


def make_sec_group_rule(net, project):
    """Enable every kind of communication (icmp, http, ssh) in `project`.

    Args:
        net: Proxy for network aka neutron [1]
        project: An OpenStack project [2]

    Refs:
        [1] https://docs.openstack.org/openstacksdk/latest/user/proxies/network.html
        [2] https://docs.openstack.org/openstacksdk/latest/user/resources/identity/v3/project.html#openstack.identity.v3.project.Project
    """
    # Delete default security group rules
    sgrs = [sgr for sgr in net.security_group_rules()
                if sgr.project_id == project.id]
    for sgr in sgrs:
        net.delete_security_group_rule(sgr)
        LOG.info("Delete sgr %s" % sgr)

    # Find the sec group for this project
    sg_default = net.find_security_group("default", project_id=project.id)

    # Let all traffic goes in/out
    protocols = ["icmp", "udp", "tcp"]
    directions = ["ingress", "egress"]
    crit = [(p, d) for p in protocols for d in directions]

    for (p, d) in crit:
        sgr = net.create_security_group_rule(
            direction=d,
            ether_type="IPv4",
            port_range_min=None if p == "icmp" else 1,
            port_range_max=None if p == "icmp" else 65535,
            project_id=project.id,
            protocol=p,
            remote_ip_prefix="0.0.0.0/0",
            security_group_id=sg_default.id)

        LOG.info("Created a new sgr %s" % sgr)


cloud = make_cloud()
project = make_account(cloud.identity, [
    "Leonardo", "Michelangelo", "Donatello", "Raphael"])
priv_snet = make_private_net(cloud.network, project)
make_router(cloud.network, project, priv_snet)
make_sec_group_rule(cloud.network, project)
