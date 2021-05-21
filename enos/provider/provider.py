# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, MutableMapping, Tuple
from enos.provider.host import Host


# XXX: We define Networks and Roles here explicitly, because importing
# enoslib.type takes 2 seconds.
Networks = List[Dict[Any, Any]]
Roles = MutableMapping[str, List[Host]]


class Provider:
    __metaclass__ = ABCMeta

    @abstractmethod
    def init(self,
             config: Dict[str, Any],
             force: bool = False) -> Tuple[Roles, Networks]:
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
    def destroy(self, env):
        "Destroy the resources used for the deployment."
        pass

    @abstractmethod
    def default_config(self) -> Dict[str, Any]:
        """The default provider configuration.

        Returns a dict with all keys used to initialise the provider
        (section `provider` of reservation.yaml file). Keys should be
        provided with a default value. Keys set with `None` value must
        be override in the reservation.yaml.

        """
        pass
