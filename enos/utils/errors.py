class EnosError(Exception):
    pass


class EnosFailedHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosUnreachableHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosProviderMissingConfigurationKeys(EnosError):
    def __init__(self, missing_overridden):
        super(EnosProviderMissingConfigurationKeys, self).__init__(
            "Keys %s have to be overridden in the provider "
            "section of the reservation file."
            % missing_overridden)
        self.missing_ovorridden = missing_overridden
