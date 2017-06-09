import openstack


class Chameleonkvm(openstack.Openstack):
    def init(self, conf, calldir, force_deploy=False):
        return super(Chameleonkvm, self).init(conf, calldir, force_deploy)

    def destroy(self, calldir, env):
        super(Chameleonkvm, self).destroy(calldir, env)

    def default_config(self):
        default_config = super(Chameleonkvm, self).default_config()
        default_config.update({
            'type': 'chameleonkvm',
            'image_name': 'CC-Ubuntu16.04',
            'user': 'cc',
            'dns_nameservers': ['129.114.97.1',
                                '129.114.97.2',
                                '129.116.84.203'],
            'network_interface': 'ens3'
        })

        return default_config
