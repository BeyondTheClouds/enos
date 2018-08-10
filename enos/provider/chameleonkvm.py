import enos.provider.openstack as openstack

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
        return super(Chameleonkvm, self).init(conf, force_deploy)

    def destroy(self, env):
        super(Chameleonkvm, self).destroy(env)

    def default_config(self):
        default_config = super(Chameleonkvm, self).default_config()
        default_config.update(DEFAULT_CONFIG)
        return default_config
