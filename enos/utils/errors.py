# -*- coding: utf-8 -*-

class EnosError(Exception):
    pass


class EnosFailedHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosUnreachableHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosFilePathError(EnosError):
    def __init__(self, filepath, msg=''):
        super(EnosFilePathError, self).__init__(msg)
        self.filepath = filepath


class EnosUnknownProvider(EnosError):
    def __init__(self, provider_name):
        super(EnosUnknownProvider, self).__init__(
            f"The provider '{provider_name}' could not be found.  "
            "Please refer to https://beyondtheclouds.github.io/enos/provider/ "
            "to use a provider that exists.")

        self.provider_name = provider_name


class MissingEnvState(EnosError):
    def __init__(self, key):
        super(MissingEnvState, self).__init__(
            f"The key '{key}' does not appears in the enos environment.")

        self.key = key
