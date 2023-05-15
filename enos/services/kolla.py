# -*- coding: utf-8 -*-
"Installs kolla-ansible locally in a dedicated virtual environment"
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import enoslib as elib
import yaml
from ansible.plugins.loader import filter_loader as ansible_filter_loader
from enos.utils import constants as C

# Default kolla-ansible package to install (OpenStack Wallaby)
KOLLA_PKG = 'kolla-ansible~=12.0'

# Kolla recommends installing ansible manually.  Currently 2.9 is supported.
# Refers to the kolla-ansible User Guides for future versions. See,
# https://docs.openstack.org/kolla-ansible/stein/user/quickstart.html#install-dependencies-not-using-a-virtual-environment
ANSIBLE_PKG = 'ansible>=2.9,<2.10'

# Current python version
PY_VERSION = f'python{sys.version_info.major}.{sys.version_info.minor}'

# Path to the passwords.yml file
PASSWORDS_PATH = Path(C.RSCS_DIR) / 'passwords.yml'

# Path to the default globals.yml file.  This path is relative to the virtual
# environment and thus should be joined with the instance attribute
# `self.venv_path`.  See,
# https://docs.openstack.org/kolla-ansible/ussuri/user/quickstart.html
DEFAULT_GLOBALS_PATH = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'group_vars', 'all.yml')

# Path to specific kolla-ansible jinja2 filters.  kolla-ansible developed new
# filters such as `put_address_in_context` to manage IPv6 [0]. This path is
# relative to the virtual environment and thus should be joined with the
# instance attribute `self.venv_path`.  How to load local filters is documented
# in [1].  There is also a specific method `add_directory` on plugin loader[2]:
#
# > from ansible.plugins.loader import filter_loader
# > filter_loader.add_directory(os.path.join(ka.venv_path, KOLLA_FILTERS))
#
# [0]https://github.com/openstack/kolla-ansible/commit/bc053c09c180b21151da9312386c0d2fdc1a2700
# [1]https://docs.ansible.com/ansible/latest/dev_guide/developing_locally.html
# [2]https://github.com/ansible/ansible/blob/7fa32b9b44a229bfdd44811832eec0010b36afd1/lib/ansible/plugins/loader.py#L296
KOLLA_FILTERS = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'filter_plugins')

# Path to the ansible kolla_toolbox module.  This path is relative to the
# virtual environment and thus should be joined with the instance attribute
# `self.venv_path`.  We should be able to do something like the following to
# load it in ansible :
#
# from ansible.plugins.loader import module_loader
# module_loader.add_directory(os.path.join(ka.venv_path, KOLLA_TOOLBOX))
KOLLA_TOOLBOX = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'library')


# XXX: Proper handling of kolla networks.
# Remember to remove NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE, that are in
# the inventory from the globals_values.


class KollaAnsible(object):
    # Path to the virtual environment of this kolla-ansible
    venv_path: Path

    # List of arguments to run kolla-ansible (e.g., --configdir <cfg>,
    # --inventory <inv>, ...)
    kolla_args: List[str]

    # All values from the globals.yml (including kolla-ansible default ones).
    #
    # Note(rcherrueau): Many values are variables and some could not be used
    # directly in enoslib because they rely on filters `KOLLA_FILTERS` and the
    # module `KOLLA_TOOLBOX`.
    globals_values: Dict[str, Any]

    # Inventory used by kolla-ansible.
    _inventory: Path

    def __init__(self,
                 config_dir: Path,
                 inventory_path: str,
                 pip_package: Optional[str] = None,
                 globals_values={}) -> None:
        """Installs kolla-ansible locally in a dedicated virtual environment.

        The virtual environment is created at `config_dir`. It its named after
        the `pip_package`.  If a virtual environment already exists with the
        same name it is not recreated/installed.  The `globals.yml` is created
        during the deployment.  Authentication variables are resolved with
        an extra call to a local Ansible.  They are available under
        `self.globals_values.get('openstack_auth')`.

        Args:
          config_dir: Path to the directory that will contains the
              `globals.yml`.
          inventory_path:  Path to the inventory file.
          pip_package: The kolla-ansible pip package to install.  Package could
              be specified using the pip package syntax.  For instance, a PyPi
              package 'kolla-ansible==2.9.0', a git repository
              'git+https://github.com/openstack/kolla-ansible.git@stable/ussuri',
              or a local editable directory '-e ~/path/to/loca/kolla-ansible'.
              Defaults to `KOLLA_PKG`.
          globals_values: Override kolla-ansible values for the `globals.yml`.

        This class offers the method `execute` to execute kolla-ansible
        commands. Example:

        .. code-block:: python

          kolla = KollaAnsible(
              pathlib.Path('/tmp'), '', 'kolla-ansible~=10.0',
              {'kolla_internal_vip_address': ''})
          kolla.execute(['bootstrap-servers'])
          kolla.execute(['deploy', '--help'])

        The method `get_admin_openrc_env_values` formats and returns
        authentication values as in the admin-openrc file. Example:

        .. code-block:: python

          print(kolla.get_admin_openrc_env_values())
          {
            "OS_AUTH_URL": "http://192.168.42.243:5000/",
            "OS_USER_NAME": "admin",
            # ...
            "OS_IDENTITY_API_VERSION": "3"
          }

        """
        # Install kolla-ansible
        self.venv_path = KollaAnsible.pull(
            pip_package if pip_package is not None else KOLLA_PKG,
            config_dir)

        # Compute kolla-ansible args and globals
        self._inventory = Path(inventory_path)
        self.globals_values = self._gen_globals_and_yml(
            config_dir, globals_values)
        self.kolla_args = self._mk_kolla_args(
            config_dir, PASSWORDS_PATH)

    def execute(self, operation: List[str]) -> None:
        'Executes an operation on kolla-ansible'
        # Call kolla-ansible executable ...
        cmd = [f'{self.venv_path}/bin/kolla-ansible']
        # ... with proper arguments ...
        cmd += self.kolla_args
        # ... and the specific `operation`
        cmd += operation

        self._execute_in_venv(cmd)

    def _execute_in_venv(self, cmd: List[str]):
        'Executes a command into the virtual environment of this kolla-ansible'
        venv_cmd = [f'. {self.venv_path}/bin/activate &&'] + cmd
        logging.debug(f'Executing {venv_cmd} ...')
        subprocess.run(' '.join(venv_cmd), shell=True, check=True)

    def _mk_kolla_args(self, config_dir: Path,
                       password_path: Path) -> List[str]:
        'Computes the list of arguments to run kolla-ansible'
        return ['--configdir ' + str(config_dir),
                '--inventory ' + str(self._inventory),
                '--passwords ' + str(password_path)]

    def _gen_globals_and_yml(
            self,
            config_dir: Path,
            globals_values: Dict[str, Any]) -> Dict[str, Any]:
        """Generates and writes the globals in the `config_dir`.

        This generates all globals values.  It includes kolla-ansible default
        ones overrided by Enos ones (e.g., `kolla_internal_vip_address`).  A
        local Ansible call also resolves the `openstack_auth` variable that
        contains OpenStack connection information.

        """
        all_values = {}

        # Get kolla-ansible default globals
        with open(self.venv_path / DEFAULT_GLOBALS_PATH) as f:
            all_values.update(yaml.safe_load(f))

        # Get Enos passwords
        with open(PASSWORDS_PATH) as f:
            all_values.update(yaml.safe_load(f))

        # These two interfaces are set in the host vars.  We don't need them
        # here since they will overwrite those in the inventory
        all_values.pop(C.NEUTRON_EXTERNAL_INTERFACE, None)
        all_values.pop(C.NETWORK_INTERFACE, None)

        # Override with the provided (Enos) globals values
        all_values.update(globals_values)

        # Compute `openstack_auth` values.
        all_values.update(
            openstack_auth=self._resolve_openstack_auth(all_values))

        # Put the final result into the `globals.yml`
        with open(config_dir / 'globals.yml', 'w') as f:
            yaml.dump(all_values, f, default_flow_style=False)

        return all_values

    def _resolve_openstack_auth(
            self, globals_values: Dict[str, Any]) -> Dict[str, Any]:
        "Compute and returns the value of `globals_values['openstack_auth']`"

        # Get the former system paths.  We latter load kolla (required by the
        # `put_address_in_context` filter) and change that path.
        old_sys_paths = sys.path.copy()

        # Temporary file to later store the result of the rendered
        # `openstack_auth` variable by Ansible.
        _, osauth_path = tempfile.mkstemp()

        try:
            # Load kolla-ansible specific filters `KOLLA_FILTERS` since the
            # `{{openstack_auth}}` variable relies on the
            # `put_address_in_context` filter to manage IPv6.
            #
            # Note(rcherrueau): we also have to load kolla_ansible because the
            # filter in `KOLLA_FILTERS` does something like `form kolla_ansible
            # import filters`.  We load kolla_ansible from the virtual_env in
            # the system path.  In that case, pbr may complain with: Versioning
            # for this project requires either an sdist tarball, or access
            # to an upstream git repository.  We set pbr to version '1.2.3' to
            # disable all version calculation logic by pbr [0].
            # [0]https://docs.openstack.org/pbr/latest/user/packagers.html#versioning
            ansible_filter_loader.add_directory(
                str(self.venv_path / KOLLA_FILTERS))
            sys.path.append(
                str(self.venv_path / 'lib' / PY_VERSION / 'site-packages'))
            os.environ['PBR_VERSION'] = '1.2.3'

            # Render `openstack_auth` into `osauth_path`
            with elib.play_on(roles={}, pattern_hosts="localhost",
                              extra_vars=globals_values) as yaml:
                yaml.local_action(
                    **title('Compute values of `openstack_auth`'),
                    module="copy",
                    content="{{ openstack_auth }}",
                    dest=osauth_path)

            # Read and return the rendered values from `osauth_path`
            with open(osauth_path, 'r') as rc_yaml:
                return json.load(rc_yaml)

        finally:
            # Delete temporary `osauth_path` file
            os.unlink(osauth_path)
            # Reset system paths
            sys.path = old_sys_paths

    def get_admin_openrc_env_values(self) -> Dict[str, str]:
        '''Returns environment variables to authenticate on OpenStack.

        The returned dict is similar to variables and values inside the
        `admin-openrc` file.

        '''
        os_auth_rc = {f'OS_{auth_key.upper()}': auth_value
                      for auth_key, auth_value
                      in self.globals_values.get('openstack_auth', {}).items()}
        os_auth_rc.update({
            'OS_REGION_NAME': (self.globals_values
                               .get('openstack_region_name', '')),
            'OS_IDENTITY_API_VERSION': '3',
            'OS_INTERFACE': 'internal',
            'OS_AUTH_PLUGIN': 'password',
        })

        return os_auth_rc

    def backup(self, destination: Path):
        'Backup kolla-ansible logs and conf'
        logging.info('Backup kolla-ansible logs and conf')
        with elib.play_on(inventory_path=str(self._inventory),
                          extra_vars=self.globals_values) as yaml:
            yaml.archive(
                **title('Archive kolla-ansible logs and conf'),
                format='gz',
                path=[
                    # kolla-ansible logs
                    '/var/lib/docker/volumes/kolla_logs/_data',
                    # kolla-ansible conf
                    '/etc/kolla'],
                dest='/tmp/kolla-log+conf.tar.gz')

            yaml.fetch(
                **title('Fetch kolla-ansible logs and conf'),
                flat=True,
                src='/tmp/kolla-log+conf.tar.gz',
                dest=(str(destination)
                      + '/{{ inventory_hostname }}-kolla-log+conf.tar.gz'))

    def destroy(self, include_images: bool = False, verbose: bool = False):
        cmd = ['destroy', '--yes-i-really-really-mean-it']

        if include_images:
            cmd.append('--include-images')
        if verbose:
            cmd.append('verbose')

        self.execute(cmd)

    @staticmethod
    def pull(pip_package: str, config_dir: Path) -> Path:
        '''Install kolla-ansible in a virtual environment at `config_dir`.

        The name of the virtual environment is computed based on the
        `pip_package`, so calling that method with two different `pip_package`
        values results in two different installations.

        Args:
            pip_package: The kolla-ansible pip package to install.  Package
              could be specified using the pip package syntax.  For instance,
              a PyPi package 'kolla-ansible==2.9.0', a git repository
              'git+https://github.com/openstack/kolla-ansible.git@stable/ussuri',
              or a local editable directory '-e ~/path/to/loca/kolla-ansible'.
            config_dir:  Directory to install kolla-ansible in.
        '''
        logging.info("Installing kolla-ansible and dependencies...")

        # Generates a path for the virtual environment computing a
        # deterministic hash, See https://stackoverflow.com/a/42089311
        pip_ref_hash = int(hashlib.sha256(pip_package.encode('utf-8'))
                           .hexdigest(), 16) % 10**8
        venv = (config_dir / f'kolla-ansible-venv-{pip_ref_hash}').resolve()

        # Install kolla-ansible and its dependencies
        with elib.play_on(roles={}, pattern_hosts="localhost") as yaml:
            yaml.local_action(
                **title(f'Install {pip_package} in {venv}'),
                module="pip",
                # Pin Jinja2 version to fix the renaming of `contextfilter`
                # into `pass_context.evalcontextfilter`.
                # See https://github.com/BeyondTheClouds/enos/pull/346#issuecomment-1080851796  # noqa
                # requests/urllib3 bug: https://github.com/docker/docker-py/issues/3113  # noqa
                name=[ANSIBLE_PKG, 'Jinja2==3.0.3', 'requests<2.29', 'urllib3<2',
                      'influxdb', pip_package],
                virtualenv=str(venv),
                virtualenv_python=PY_VERSION)

        return venv


def title(title: str) -> Dict[str, str]:
    "A title for an ansible yaml commands"
    return {"task_name": "Kolla : " + title}
