import enos.provider.openstack as openstack
from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm as Eckvm
from enoslib.infra.enos_chameleonkvm.configuration import Configuration

import logging

# - SPHINX_DEFAULT_CONFIG
DEFAULT_CONFIG = {
    'type': 'chameleonkvm',
    'image': 'CC-Ubuntu16.04',
    'user': 'cc',
    'dns_nameservers': ['129.114.97.1',
                        '129.114.97.2',
                        '129.116.84.203']
}
# + SPHINX_DEFAULT_CONFIG


class Chameleonkvm(openstack.Openstack):
    def init(self, conf, force_deploy=False):
        logging.info("Chameleonkvm provider")
        enoslib_conf = self.build_config(conf)
        _conf = Configuration.from_dictionnary(enoslib_conf)
        eckvm = Eckvm(_conf)
        roles, networks = eckvm.init(force_deploy=force_deploy)
        return roles, networks

    def destroy(self, env):
        super(Chameleonkvm, self).destroy(env)

    def default_config(self):
        default_config = super(Chameleonkvm, self).default_config()
        default_config.update(DEFAULT_CONFIG)
        return default_config

    def __str__(self):
        return "Chameleonkvm"
