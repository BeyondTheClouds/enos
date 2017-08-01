class Host(object):

    def __init__(
            self,
            address,
            alias=None,
            user=None,
            keyfile=None,
            port=None,
            extra=None):
        self.address = address
        self.alias = alias
        if self.alias is None:
            self.alias = address
        self.user = user
        self.keyfile = keyfile
        self.port = port
        self.extra = extra or {}

    def __repr__(self):
        args = [self.alias, "address=%s" % self.address]
        return "Host(%s)" % ", ".join(args)

    def __str__(self):
        args = [self.alias, "address=%s" % self.address, "user=%s" %
                self.user, "keyfile=%s" % self.keyfile, "port=%s" %
                self.port, "extra=%s" % self.extra]
        return "Host(%s)" % ", ".join(args)
