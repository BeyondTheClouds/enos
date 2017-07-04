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

        network = config['provider']['network']
        eths = config['provider']['eths']
        roles = {r: _make_hosts(vs) for (r, vs) in config['resources'].items()}

        return (roles, network, eths)

    def destroy(self, env):
        logging.warning('Resource destruction is not implemented '
                        'for the static provider. Call `enos destroy` '
                        '(without --hard) to delete OpenStack containers.')

    def default_config(self):
        return {
            'network': None,  # A dict to configure the network with
                              # `start` the first available ip, `end`
                              # the last available ip, `cidr` the
                              # network of available ips, the ip
                              # address of the `gateway` and the ip
                              # address of the `dns`,
                              # `extra_ips` is an array of vips to be asssigned
                              # during the deployment

            'eths':    None   # A pair that contains the name of
                              # network and external interfaces
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
