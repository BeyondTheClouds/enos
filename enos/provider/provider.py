# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod


class Provider:
    __metaclass__ = ABCMeta

    @abstractmethod
    def init(self, config, force=False):
        """Provides resources and provisions the environment.

        The `config` parameter contains the client request (eg, number
        of compute per role among other things). This method returns a
        list of the form [{Role: [Host]}], a pool of 5 ips, and a usable
        provider external network.
        """
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
