from jinja2 import Template

import json


BASE_TEMPLATE = {
    'enable_monitoring': True,
    'inventory': 'inventories/inventory.sample',
    'kolla': {
        'enable_heat': 'yes',
        'kolla_base_distro': '{{ base }}',
        'kolla_install_type': '{{ distribution }}',
        'nova_compute_virt_type': 'qemu'
    },
    'kolla_ref': 'stable/rocky',
    'kolla_repo': 'https://git.openstack.org/openstack/kolla-ansible',
    'registry': {
        'type': 'internal'
    },
    'working_dir': '{{ directory }}',
    'strategy': 'copy'
}

VAGRANT_TEMPLATE = {
    'provider': {
        'backend': '{{ backend }}',
        'box': '{{ box }}',
        'type': 'vagrant',
        'resources': {
            'machines': [
                {
                    'roles': ['control', 'compute', 'network'],
                    'number': 1,
                    'flavour': 'extra-large'
                }],
            'networks': [
                {
                    'cidr': '192.168.100.0/24',
                    'roles': ['network_interface']
                },
                {
                    'cidr': '192.168.200.0/24',
                    'roles': ['neutron_external_interface']
                }]
        }
    }
}


G5K_TEMPLATE = {
    'provider': {
        'job_name': 'enos-build-g5k',
        'type': 'g5k',
        'env_name': '{{ environment }}',
        'walltime': '01:00:00',
        'resources': {
            'machines': [
                {
                    'cluster': '{{ cluster }}',
                    'nodes': 1,
                    'roles': ['control', 'compute', 'network'],
                    'primary_network': 'int-net',
                    'secondary_networks': []
                }],
            'networks': [
                {
                    'id': 'int-net',
                    'roles': ['network_interface'],
                    'site': 'rennes',
                    'type': 'kavlan'
                }]
        }
    }
}


VMONG5K_TEMPLATE = {
    'provider': {
        'job_name': 'enos-build-vmong5k',
        'type': 'vmong5k',
        'walltime': '01:00:00',
        'image': '{{ image }}',
        'resources': {
            'machines': [
                {
                    'cluster': '{{ cluster }}',
                    'nodes': 1,
                    'roles': ['control', 'compute', 'network']
                }],
            'networks': ['network_interface']
        }
    }
}


def _instantiate_template(template, **kwargs):
    json_template = json.dumps(template)
    engine = Template(json_template)
    instance = engine.render(**kwargs)
    return json.loads(instance)


def create_configuration(provider, **kwargs):
    template = {
        'vagrant': VAGRANT_TEMPLATE,
        'g5k': G5K_TEMPLATE,
        'vmong5k': VMONG5K_TEMPLATE
    }[provider]  # raise exception for unknown providers

    # NOTE(jrbalderrama): Instantiating the template works because cli
    # provides defaults. IMHO putting defaults in documentation is fishy
    # because it does not enforce checking when they are modified in the
    # source code and specially because resulting code is kind of obscure.
    base_config = _instantiate_template(BASE_TEMPLATE, **kwargs)
    provider_config = _instantiate_template(template, **kwargs)
    return {**base_config, **provider_config}
