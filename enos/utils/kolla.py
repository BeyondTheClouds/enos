# -*- coding: utf-8 -*-
import hashlib
import os
import pathlib
import subprocess
import logging
import tempfile

import yaml
import json

from enos.utils.constants import (RSCS_DIR, NEUTRON_EXTERNAL_INTERFACE,
                                  NETWORK_INTERFACE)

from typing import (Union, List, Dict, Any)
Path = Union[str, pathlib.Path]

logger = logging.getLogger(__name__)


# Kolla recommends installing ansible manually.  Currently 2.9 is supported,
# not sure about the future So we hard-code the version to something
# reasonnable for now.
ANSIBLE_VERSION = 'ansible>=2.9,<2.10'

# passwords.yml file
PASSWORDS_PATH = os.path.join(RSCS_DIR, 'passwords.yml')

# Default globals.yml path.  This path should be joined with the instance
# attribute `self.venv_path`.
# See, https://docs.openstack.org/kolla-ansible/ussuri/user/quickstart.html
DEFAULT_GLOBALS_PATH = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'group_vars', 'all.yml')

# kolla-ansible developed new ansible filters such as `put_address_in_context`
# to manage IPv6 [0]. This path should be joined with the instance attribute
# `self.venv_path`.  How to load local filters is documented in [1].
#
# [0] https://github.com/openstack/kolla-ansible/commit/bc053c09c180b21151da9312386c0d2fdc1a2700
# [1] https://docs.ansible.com/ansible/latest/dev_guide/developing_locally.html
KOLLA_FILTERS = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'filter_plugins')

KOLLA_TOOLBOX = os.path.join(
    'share', 'kolla-ansible', 'ansible', 'library')

# TODO: Proper handling of kolla networks.
# Remember to remove NEUTRON_EXTERNAL_INTERFACE, NETWORK_INTERFACE, that are in
# the inventory from the globals_values.


class KollaAnsible(object):
    # Path to the virtual environment of this kolla-ansible
    venv_path: Path

    # List of required arguments to run kolla-ansible (e.g., --configdir,
    # --inventory, ...)
    kolla_args: List[str]

    # All values from the globals.yml (including kolla-ansible default ones)
    globals_values: Dict[str, Any]

    def __init__(self,
                 pip_package: str,
                 inventory_path: Path,
                 config_dir: Path,
                 globals_values={}) -> None:
        """Installs kolla-ansible locally in a dedicated virtual environment.

        The virtual environment is created at `config_dir`. It its named using
        the static method `gen_venv_path`.  If a virtual environment already
        exists with the same name it is not recreated/installed.  The
        `globals.yml` is also created during the instantiation and
        authentication variables will be available under
        `globals_values.get('openstack_auth)`.

        Args:
          pip_package: The kolla-ansible pip package to install.  Package could
              be specified using the pip package syntax.  For instance, a PyPi
              package 'kolla-ansible==2.9.0', a git repository
              'git+https://github.com/openstack/kolla-ansible.git@stable/ussuri',
              or a local editable directory '-e ~/path/to/loca/kolla-ansible'.
          inventory_path:  Path to the inventory file.
          config_dir: Path to the directory that will contains the
              `globals.yml`.
          globals_values: Override kolla-ansible values for the `globals.yml`.

        This class offers the method `execute` to execute kolla-ansible
        commands. Example:

        .. code-block:: python

          ka = KollaAnsible('kolla-ansible==10.0.0', ...)
          ka.execute('--help')
          ka.execute('bootstrap-servers')

        """
        self.venv_path = KollaAnsible.gen_venv_path(config_dir, pip_package)
        self.kolla_args = KollaAnsible._mk_kolla_args(
            config_dir, inventory_path, PASSWORDS_PATH)

        self._install_kolla(pip_package)
        self.globals_values = self._gen_globals_and_yml(
            config_dir, globals_values, inventory_path)

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
        # Checks that the virtual environment exists and creates it otherwise.
        if not os.path.isdir(self.venv_path):
            logger.debug(f'Creating venv {self.venv_path} ...')
            subprocess.run(f'virtualenv -p python3 {self.venv_path}',
                           shell=True, check=True)

        # Executes the `cmd` in the virtual environment
        venv_cmd = [f'. {self.venv_path}/bin/activate &&'] + cmd
        logger.debug(f'Executing {venv_cmd} ...')
        subprocess.run(' '.join(venv_cmd), shell=True, check=True)

    def _install_kolla(self, pip_kolla_package) -> None:
        'Installs kolla ansible and its dependencies'
        logger.info("Installing kolla-ansible and dependencies...")
        pip_packages = [f'"{package}"' for package in
                        (ANSIBLE_VERSION, 'influxdb', pip_kolla_package)]
        self._execute_in_venv(['pip install'] + pip_packages)

    def _gen_globals_and_yml(
            self,
            config_dir: Path,
            globals_values: Dict[str, Any],
            inventory_path: Path) -> Dict[str, Any]:
        """Generates and writes the globals in the `config_dir`.

        This generates all globals values. It includes kolla-ansible default
        ones overrided by Enos ones (e.g., `kolla_internal_vip_address`).  A
        local Ansible call also resolves the `openstack_auth` variable that
        contains OpenStack connection information.

        """
        all_values = {}

        # Get kolla-ansible default globals
        with open(os.path.join(self.venv_path, DEFAULT_GLOBALS_PATH)) as f:
            default_kolla_values = yaml.safe_load(f)

            # XXX osef
            # # Instantiate the default_kolla_values to get real values.
            # kolla_toolbox_image = default_kolla_values['docker_namespace'] + '/' + \
            #     default_kolla_values['kolla_base_distro'] + '-' + \
            #     default_kolla_values['kolla_install_type'] + '-kolla-toolbox:' + \
            #     default_kolla_values['openstack_release']

            all_values.update(default_kolla_values)

        # These two interfaces are set in the host vars.  We don't need them
        # here since they will overwrite those in the inventory
        all_values.pop(NEUTRON_EXTERNAL_INTERFACE, None)
        all_values.pop(NETWORK_INTERFACE, None)

        # Override with the provided (Enos) globals values
        all_values.update(globals_values)

        # Compute openstack_auth values.
        all_values.update(openstack_auth=self._resolve_openstack_auth(
            inventory_path, all_values))

        # Put the end results into the globals.yml
        with open(os.path.join(config_dir, 'globals.yml'), 'w') as f:
            yaml.dump(all_values, f, default_flow_style=False)

        return all_values

    def _resolve_openstack_auth(
            self,
            inventory_path: Path,
            globals_values: Dict[str, Any]) -> Dict[str, Any]:
        "Compute and returns the value of `globals_values['openstack_auth']`"
        try:
            # Temporary file to store the results of `openstack_auth` rendered
            # by Ansible.
            _, osauth_path = tempfile.mkstemp()

            # Ask local Ansible to resolve the variable `openstack_auth`
            with tempfile.NamedTemporaryFile(mode='w') as globals_f:
                # Generate a temporary globals.yml for ansible
                yaml.dump(globals_values, globals_f, default_flow_style=False)

                # Render `openstack_auth` into `osauth_path`
                self._execute_in_venv([
                    # kolla-ansible developed new ansible filters such as
                    # `put_address_in_context` to manage IPv6.  The
                    # `ANSIBLE_FILTER_PLUGINS` enables to load the necessary
                    # filters.
                    'ANSIBLE_FILTER_PLUGINS=' +
                    os.path.join(self.venv_path, KOLLA_FILTERS),
                    'ansible localhost --connection local',
                    '--inventory=' + inventory_path,
                    '--extra-vars=@' + globals_f.name,
                    '--extra-vars=@' + PASSWORDS_PATH,
                    '--module-name=copy --args',
                    '"content={{ openstack_auth }} dest=' + osauth_path + '"'])

            # Read and return rendered values from `osauth_path`
            with open(osauth_path, 'r') as rc_yaml:
                return json.load(rc_yaml)

        finally:
            # Delete temporary `osauth_path` file
            os.unlink(osauth_path)

    def get_admin_openrc_env_values(self) -> Dict[str, str]:
        '''Returns environment variables to authenticate on OpenStack

        The returned dict is similar to variables and values inside the
        `admin-openrc` file.

        '''
        os_auth_rc = {f'OS_{auth_key.upper()}': auth_value
                      for auth_key, auth_value
                      in self.globals_values.get('openstack_auth', {}).items()}
        os_auth_rc.update({
            'OS_REGION_NAME': self.globals_values.get('openstack_region_name', ''),
            'OS_IDENTITY_API_VERSION': '3',
            'OS_INTERFACE': 'internal',
            'OS_AUTH_PLUGIN': 'password',
        })

        return os_auth_rc

    @staticmethod
    def gen_venv_path(config_dir: Path, pip_package: str) -> Path:
        'Generates the path for the virtual environment'
        # Deterministic hash https://stackoverflow.com/a/42089311
        pip_ref_hash = int(hashlib.sha256(pip_package.encode('utf-8'))
                           .hexdigest(), 16) % 10**8
        return os.path.join(config_dir, f'kolla-ansible-venv-{pip_ref_hash}')

    @staticmethod
    def _mk_kolla_args(config_dir: Path,
                       inventory_path: Path,
                       password_path: Path) -> List[str]:
        'Computes the list of required arguments to run kolla-ansible'
        return ['--configdir ' + config_dir,
                '--inventory ' + inventory_path,
                '--passwords ' + password_path]
