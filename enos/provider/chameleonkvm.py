import openstack
from ..utils.provider import load_config

PROVIDER_CONFIG = {
    'type': 'chameleonkvm',
    'image_name': 'CC-Ubuntu16.04',
    'user': 'cc',
    'dns_nameservers': ['129.114.97.1', '129.114.97.2', '129.116.84.203'],
    'network_interface': 'ens3'
}


class Chameleonkvm(openstack.Openstack):
    def init(self, config, calldir, force_deploy=False):
        conf = load_config(config, default_provider_config=PROVIDER_CONFIG)
        return super(Chameleonkvm, self).init(conf, calldir, force_deploy)

    def destroy(self, calldir, env):
        super(Chameleonkvm, self).destroy(calldir, env)
