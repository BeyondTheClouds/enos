class EnosError(Exception):
    pass


class EnosFailedHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosUnreachableHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts
