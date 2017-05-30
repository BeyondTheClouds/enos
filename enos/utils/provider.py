from extra import expand_topology, build_resources


def load_config(config, default_config={}, default_provider_config={}):
    """Load and set default values to the configuration

        Groups syntax is expanded here.
    """
    conf = default_config
    conf.update(config)
    if 'topology' in config:
        # expand the groups first
        conf['topology'] = expand_topology(config['topology'])
        # We are here using a flat combination of the resource
        # resulting in (probably) deploying one single region
        conf['resources'] = build_resources(conf['topology'])

    conf['provider'] = load_provider_config(
        conf['provider'],
        default_provider_config=default_provider_config)
    return conf


def load_provider_config(provider_config, default_provider_config={}):
    """Load a set default values for the provider configuration"""
    new_provider_config = default_provider_config
    if type(provider_config) is not dict:
        new_provider_config['type'] = provider_config
    else:
        new_provider_config.update(provider_config)
    return new_provider_config
