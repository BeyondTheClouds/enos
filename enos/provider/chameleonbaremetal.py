import enos.provider.chameleonkvm as cc
from enoslib.infra.enos_chameleonbaremetal.provider\
    import Chameleonbaremetal as Ecb
from enoslib.infra.enos_chameleonbaremetal.configuration\
    import Configuration

import logging


# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'type': 'chameleonbaremetal',
    # Name os the lease to use
    'lease_name': 'enos-lease',
    # Glance image to use
    'image': 'CC-Ubuntu16.04',
    # User to use to connect to the machines
    # (sudo will be used to configure them)
    'user': 'cc',
    # True iff Enos must configure a network stack for you
    'configure_network': False,
    # Name of the network to use or to create
    'network': {'name': 'sharednet1'},
    # Name of the subnet to use or to create
    'subnet': {'name': 'sharednet1-subnet'},
    # DNS server to use when creating network
    'dns_nameservers': ['130.202.101.6', '130.202.101.37'],
    # Experiment duration
    'walltime': '02:00:00',
}
# + SPHINX_DEFAULT_CONFIG


PORT_NAME = "enos-port"


class Chameleonbaremetal(cc.Chameleonkvm):
    def init(self, conf, force_deploy=False):
        logging.info("Chameleon baremetal provider")
        enoslib_conf = self.build_config(conf)
        _conf = Configuration.from_dictionnary(enoslib_conf)
        ecb = Ecb(_conf)
        roles, networks = ecb.init(force_deploy=force_deploy)
        return roles, networks

    def destroy(self, env):
        conf = env["config"]
        enoslib_conf = self.build_config(conf)
        ecb = Ecb(enoslib_conf)
        ecb.destroy()

    def default_config(self):
        default_config = super(Chameleonbaremetal, self).default_config()
        default_config.update(DEFAULT_CONFIG)

        return default_config

    def __str__(self):
        return "Chameleonbaremetal"
