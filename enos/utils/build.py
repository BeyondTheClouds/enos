from enoslib.infra.enos_vagrant.constants import (DEFAULT_BOX,
                                                  DEFAULT_BACKEND)
from enoslib.infra.enos_vmong5k.constants import (DEFAULT_IMAGE)
#                                                  DEFAULT_WORKING_DIR)

from jinja2 import Template

import json

DEFAULT_TYPE = 'binary'

DEFAULT_BASE = 'centos'

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
    }

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
                    'roles': ['control', 'compute', 'network'],
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
        'g5k': VAGRANT_TEMPLATE,
        'vmong5k': VMONG5K_TEMPLATE
    }[provider]  # raise exception for unknown providers

    # NOTE(jrbalderrama): Instantiating the template works because cli
    # provides defaults. IMHO putting defaults in documentation is fishy
    # because it does not enforce checking when they are modified in the
    # source code and specially because resulting code is kind of obscure.
    base_config = _instantiate_template(BASE_TEMPLATE, **kwargs)
    provider_config = _instantiate_template(template, **kwargs)
    return {**base_config, **provider_config}


# filter empty arguments from cli
# arguments = {k: v for k, v in kwargs.items() if v is not None}

# def create_configuration(provider, **kwargs):
#     return {
#         'vagrant': _create_config_for_vagrant,
#         'g5k': _create_config_for_g5k,
#         'vmong5k': _create_config_for_vmong5k
#     }.get(provider, lambda **_: None)(**kwargs)
#
#
# def _create_base_config(base=DEFAULT_BASE, distribution=DEFAULT_TYPE):
#     return _instantiate_template(BASE_TEMPLATE, base=base,
#                                  distribution=distribution)
#
#
# def _create_config_for_vagrant(*, base, distribution,
#                                backend=DEFAULT_BACKEND, box=DEFAULT_BOX):
#     base_config = _create_base_config(base=base, distribution=distribution)
#     vagrant_config = _instantiate_template(VAGRANT_TEMPLATE,
#                                            backend=backend, box=box)
#
#     # return merge configurations
#     return {**base_config, **vagrant_config}
#
#
# def _create_config_for_g5k(*, base, distribution, cluster=None):
#     pass
#
#
# def _create_config_for_vmong5k(*, base, distribution, box=DEFAULT_BOX,
#                                cluster=None, image=None):
#     pass
