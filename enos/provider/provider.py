# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod


class Provider:
    __metaclass__ = ABCMeta

    @abstractmethod
    def init(self, config, calldir, force=False):
        """Provides resources and provisions the environment.

        The `config` parameter contains the client request (eg, number
        of compute per role among other things). This method returns,
        in this order, a list of the form [{Role: [Host]}], a dict
        with `cidr`, `gateway` and `dns` to set the network, and a
        pair that contains the name of network and external
        interfaces.

        """
        pass

    @abstractmethod
    def destroy(self, calldir, env):
        """Destroy the resources used for the deployment"""
        pass

    def before_preintsall(self, env):
        """Returns ansible tasks executed before the preinstall phase.

        This method should be stateless.

        """
        return ""

    def after_preintsall(self, env):
        """Returns ansible tasks executed after the preinstall phase.

        This method should be stateless.

        """
        return ""
