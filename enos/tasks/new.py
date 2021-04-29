import logging
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import jinja2
import yaml
import enos.utils.constants as C
from enos.services import kolla
from enos.utils.extra import make_provider

logger = logging.getLogger(__name__)

# Resources definitions
G5K_RSC = {'paravance': {'compute': 1, 'network': 1, 'control': 1}}
VAGRANT_RSC = {
    'extra-large': {'control': 1},
    'medium': {'network': 1, 'compute': 1}
}
CHAM_KVM_RSC = {'m1.medium': {'compute': 1, 'network': 1, 'control': 1}}
CHAM_BARE_RSC = {'compute_haswell': {'compute': 1, 'network': 1, 'control': 1}}
OS_RSC = {'<set a flavor (see `openstack flavor list`)>':
          {'compute': 1, 'network': 1, 'control': 1}}
VMONG5K_RSC = {'paravance': {'compute': 1, 'network': 1, 'control': 1}}
STATIC_RSC = (
    '<refer to the doc at '
    'https://beyondtheclouds.github.io/enos/provider/static.html>')

# Registry definitions
INTERNAL_REG = {'type': 'internal', 'port': 4000}
G5K_EXTERNAL_REG = {
    'type': 'external', 'port': 80, 'ip': 'docker-cache.grid5000.fr'
}


def dump(info: Dict[str, Union[str, int]], required_keys: List[str]) -> str:
    '''Format `info` for a yaml document.

    All keys absent from `required_keys` are commented out with `#`.

    '''
    _info = info.copy()

    yaml_str = ''

    # Format required keys
    for req_key in required_keys:
        yaml_str += yaml.dump({req_key: _info.pop(req_key)})

    # Format optional keys and prefix them with a `# ` to make them a comment
    # in the resulted yaml
    for k, v in _info.items():
        yaml_str += textwrap.indent(yaml.dump({k: v}), '# ')

    return yaml_str


def get_provider_and_backend_names(provider: str) -> Tuple[str, Optional[str]]:
    '''Find the provider name and the backend name if any.

    For instance, `vagrant:virtualbox` returns (vagrant, virtualbox) and `g5k`
    return (g5k, None).

    '''
    p = provider.split(':')

    if len(p) == 1:
        return p[0], None
    else:
        return p[0], ':'.join(p[1:])


def new(provider_name: str, output_path: Path):
    # Get the provider and backend names, e.g. (g5k, None) or (vagrant,
    # virtualbox)
    provider, backend = get_provider_and_backend_names(provider_name)

    # Options for the reservation.yaml.j2 template
    provider_conf = make_provider(provider).default_config()
    provider_required_keys = ['type']
    resources_conf = None
    registry_conf = None

    # Refine options based on the provider
    if provider == 'g5k':
        resources_conf = G5K_RSC
        registry_conf = G5K_EXTERNAL_REG
        provider_required_keys += ['walltime', 'job_name']
    elif provider == 'vagrant':
        provider_conf.update(backend=backend)
        resources_conf = VAGRANT_RSC
        registry_conf = INTERNAL_REG
        provider_required_keys.append('backend')
    elif provider == 'chameleonkvm':
        provider_conf.update(
            key_name='<set a Nova SSH key (see `openstack keypair list`)>')
        registry_conf = INTERNAL_REG
        resources_conf = CHAM_KVM_RSC
        provider_required_keys.append('key_name')
    elif provider == 'chameleonbaremetal':
        provider_conf.update(
            key_name='<set a Nova SSH key (see `openstack keypair list`)>')
        registry_conf = INTERNAL_REG
        resources_conf = CHAM_BARE_RSC
        provider_required_keys += ['key_name', 'walltime']
    elif provider == 'openstack':
        provider_conf.update(
            user='<set an OpenStack user (see `openstack user list`)>',
            key_name='<set a Nova SSH key (see `openstack keypair list`)>',
            image='<set a Glance image (see `openstack image list`)>')
        registry_conf = INTERNAL_REG
        resources_conf = OS_RSC
        provider_required_keys += ['user', 'key_name', 'image']
    elif provider == 'vmong5k':
        resources_conf = VMONG5K_RSC
        registry_conf = INTERNAL_REG
        provider_required_keys += ['walltime', 'job_name']
    elif provider == 'static':
        resources_conf = STATIC_RSC
        registry_conf = INTERNAL_REG

    logger.debug(f'Generating {output_path} file with '
                 f'provider conf {provider_conf}, '
                 f'registry conf {registry_conf}, and '
                 f'resource conf {resources_conf}')

    # Render the reservation.yaml.j2 template
    with open(Path(C.TEMPLATE_DIR) / 'reservation.yaml.j2') as jinja_f,\
         open(output_path, mode='x') as res_f:
        template = jinja2.Template(jinja_f.read(), autoescape=False)
        res_f.write(template.render(
            provider=dump(provider_conf, provider_required_keys),
            resources=yaml.dump(resources_conf),
            registry=yaml.dump(registry_conf),
            kolla_ansible=kolla.KOLLA_PKG))
