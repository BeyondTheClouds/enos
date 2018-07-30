# -*- coding: utf-8 -*-
from provider import Provider
from host import Host

import logging


class Static(Provider):
    def init(self, config, force=False):
        raise Exception("TODO, not implemented yet")

    def destroy(self, env):
        raise Exception("TODO, not implemented yet")

    def default_config(self):
        raise Exception("TODO, not implemented yet")

