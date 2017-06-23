# -*- coding: utf-8 -*-
from provider import Provider
from host import Host

import logging


class Static(Provider):
    def init(self, config, force=False):
        def _make_hosts(resource):
            """Builds Host objects for `resource`.

            A `resource` can be either (i) a dict with Host entries,
            or (ii) a list of Host entries.
            """
            if isinstance(resource, list):
                return sum(map(_make_hosts, resource), [])
            else:
                return [Host(address=resource['address'],
                             alias=resource.get('alias', None),
                             user=resource.get('user', None),
                             keyfile=resource.get('keyfile', None),
                             port=resource.get('port', None),
                             extra=resource.get('extra', {}))]

        networks = config['provider']['networks']
        roles = {r: _make_hosts(vs) for (r, vs) in config['resources'].items()}

        return (roles, networks)

    def destroy(self, env):
        logging.warning('Resource destruction is not implemented '
                        'for the static provider. Call `enos destroy` '
                        '(without --hard) to delete OpenStack containers.')

    def default_config(self):
        return {
            'networks': None,  # An array of networks
                               # one network looks like the following
                               # {
                               #   'cidr': '192.168.0.0/24',
                               #   in case Enos needs to pick ips
                               #     e.g : Kolla vips, Openstack ext-net ...
                               #   'start': '192.168.0.10',
                               #   'end': '192.168.0.50',
                               # same as above but used in case you don't have
                               # a contiguous set of ips
                               #   'extra_ips': []
                               #   'dns': '8.8.8.8',
                               #   'gateway': '192.168.0.254'
                               # (optionnal) mapping to one kolla network
                               #   'mapto': '<kolla network name>'
        }

    def topology_to_resources(self, topology):
        resources = {}

        for grp, rsc in topology.items():
            self._update(resources, rsc)
            resources.update({grp: rsc.values()})

        return resources

    def _update(self, rsc1, rsc2):
        "Update `rsc1` by pushing element from `rsc2`"
        for k, v in rsc2.items():
            values = rsc1.setdefault(k, [])
            values.append(v)
