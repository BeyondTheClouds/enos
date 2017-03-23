class Host(object):

    def __init__(
            self,
            address,
            alias=None,
            user=None,
            keyfile=None,
            port=None,
            extra={}):
        self.address = address
        self.alias = alias
        if self.alias is None:
            self.alias = address
        self.user = user
        self.keyfile = keyfile
        self.port = port
        self.extra = extra

    def __repr__(self):
        args = [self.alias, "address=%s" % self.address]
        return "Host(%s)" % ", ".join(args)
