# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod


class Provider:
    __metaclass__ = ABCMeta

    @abstractmethod
    def init(self, config, calldir, force=False):
        """Provides resources and provisions the environment.

        The `config` parameter contains the client request (eg, number
        of compute per role among other things). This method returns,
        in this order, a list of the form [{Role: [Host]}], a dict to
        configure the network with `start` the first available ip,
        `end` the last available ip, `cidr` the network of available
        ips, the ip address of the `gateway` and the ip address of the
        `dns`, and a pair that contains the name of network and
        external interfaces.

        """
        pass

    @abstractmethod
    def destroy(self, calldir, env):
        "Destroy the resources used for the deployment."
        pass

    @abstractmethod
    def default_config(self):
        """The default provider configuration.

        Returns a dict with all keys used to initialise the provider
        (section `provider` of reservation.yaml file). Keys should be
        provided with a default value. Keys set with `None` value must
        be override in the reservation.yaml.

        """
        pass

    def topology_to_resources(self, topology):
        """
        Build the resource list
        For now we are just aggregating all the resources
        This could be part of a flat resource builder
        """
        def merge_add(cluster_roles, roles):
            """Merge two dicts, sum the values"""
            for role, nb in roles.items():
                cluster_roles.setdefault(role, 0)
                cluster_roles[role] = cluster_roles[role] + nb

        resource = {}

        for group, clusters in topology.items():
            for cluster, roles in clusters.items():
                resource.setdefault(cluster, {})
                merge_add(resource[cluster], roles)

        return resource
