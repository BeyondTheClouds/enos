# -*- coding: utf-8 -*-
"Installs Rally OpenStack on a list of agents"
import logging
import json
import uuid
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import enoslib as elib

# Virtual environment path for Rally on the remote machine
VENV = '~/rally-venv'

# Rally OpenStack package to install with pip
PKG = 'rally-openstack~=2.1.0'


class RallyOpenStack():
    # Resources with agents that have Rally
    rsc: elib.Roles

    # Name of the rally deployment
    name: str

    # Tracker of done Rally tasks [(scenario name, {hostname: Rally-uuid})]
    _tasks: List[Tuple[str, Dict[str, str]]]

    def __init__(self,
                 agents: List[elib.Host],
                 environment_name: str = 'enos'):
        """Deploy Rally OpenStack on a list of agents.

        Args:
          agents: The list of agents to deploy Rally OpenStack on.
          environment_name: Name of this rally environment.

        Reference:
          https://github.com/openstack/rally-openstack
        """
        self.rsc = agents
        self.env_name = environment_name
        self._tasks = []

        RallyOpenStack.pull(agents)

    @staticmethod
    def pull(agents: List[elib.Host]):
        'Installs Rally OpenStack'
        logging.info("Pull: installing rally in a virtual environment")

        with elib.play_on(roles=agents,
                          priors=[elib.api.__python3__],
                          gather_facts=False) as yaml:
            yaml.pip(**title(f'install virtualenv {VENV}'), name='virtualenv')

            # XXX: https://cryptography.io/en/3.4.7/installation.html#rust
            yaml.pip(**title('upgrade pip for cryptography dependency'),
                     name='pip',
                     state='latest',
                     virtualenv=VENV,
                     virtualenv_python='python3')

            # XXX: We fix the version of decorator because of a bug when doing
            # `rally task ...`. See
            # https://bugs.launchpad.net/rally/+bug/1922707
            yaml.pip(**title(f'install {PKG} in {VENV}'),
                     name=[PKG, 'decorator==4.4.2', 'sqlalchemy<2'],
                     state='present',
                     virtualenv=VENV)

    def deploy(self, openstack_auth: Dict[str, str], reset=False):
        'Deploying a Rally environment'
        logging.info(f"Deploy: Rally environment {self.env_name}")

        with elib.play_on(roles=self.rsc, gather_facts=False) as yaml:
            # Creates the rally database if it does not exist
            yaml.command(
                f'{VENV}/bin/rally db ensure',
                **title('ensure database exists'))

            if not self.env_exists() or reset:
                # Set the tracker of done tasks to 0
                self._tasks = []

                # Creates the rally environment and check that provided
                # `openstack_auth` are correct credentials
                yaml.command(
                    f"{VENV}/bin/rally env delete"
                    f"  --env='{self.env_name}' --force",
                    **title(f'delete environment {self.env_name}'),
                    ignore_errors=True)
                yaml.command(
                    f"{VENV}/bin/rally env create"
                    "   --from-sysenv --no-use"
                    f"  --name='{self.env_name}'",
                    **title(f'create environment {self.env_name}'),
                    environment=openstack_auth)
                yaml.command(
                    f"{VENV}/bin/rally env check "
                    f"  --env='{self.env_name}'",
                    **title('ensure OpenStack credentials are correct'))

    def run_scenario(self,
                     scenario: Path,
                     arguments: Dict[str, Any],
                     plugin: Optional[Path] = None,
                     pattern_hosts: str = "all"):
        'Execute the Rally local `scenario` with `arguments`.'
        logging.info(f"Running rally {scenario} in env {self.env_name}")

        scenario_name = scenario.name
        scenario_local_path = str(scenario)
        scenario_remote_path = f'~/{scenario_name}'
        plugin_remote_path = '~/plugin'
        _tag = scenario_name + '-' + str(uuid.uuid4())

        # Executing the scenario
        logging.debug(f'Executing scenario {scenario_name} with tag {_tag}...')
        with elib.play_on(roles=self.rsc,
                          pattern_hosts=pattern_hosts,
                          gather_facts=False) as yaml:
            # Setup the scenario
            yaml.copy(
                **title(f'copy {scenario_name}'),
                src=scenario_local_path,
                dest=scenario_remote_path)

            # Copy plugin if any
            if plugin:
                yaml.copy(**title(f'copy rally plugin {plugin}'),
                          src=str(plugin),
                          dest=plugin_remote_path)

            # Run the scenario
            yaml.command(
                (f'{VENV}/bin/rally'
                 + (f' --plugin-paths {plugin_remote_path}' if plugin else '')
                 + f' task start {scenario_remote_path}'
                 + f' --task-args={shlex.quote(json.dumps(arguments))}'
                 + f' --tag="{_tag}"'
                 + f' --deployment="{self.env_name}"'),
                ignore_errors=True,
                **title(f'execute {scenario_name} (may take a while...)'))

        # Get the uuid and mark the scenario done in the tasks tracker
        uuid_by_hosts = {
            result.host: result.payload['stdout']
            for result
            in elib.run_command(
                f'{VENV}/bin/rally task list --uuids-only'
                f'  --deployment="{self.env_name}"'
                f'  --tag {_tag}',
                roles=self.rsc,
                pattern_hosts=pattern_hosts)}

        logging.info(f"Scenario finished with uuid {uuid_by_hosts}")
        self._tasks.append((scenario_name, uuid_by_hosts))

    def backup(self, destination: Path, pattern_hosts: str = "all"):
        'Generates json/html reports and backup them'
        logging.info(f"Backup Rally reports for tasks {self._tasks}")

        # Index the list of uuids by hosts
        hosts_uuids = {}
        for _, uuid_by_hosts in self._tasks:
            for host, _uuid in uuid_by_hosts.items():
                uuids = hosts_uuids.setdefault(host, [])
                uuids.append(_uuid)

        with elib.play_on(roles=self.rsc,
                          pattern_hosts=pattern_hosts,
                          gather_facts=False) as yaml:
            # Generate html and json reports for all tasks
            for host, uuids in hosts_uuids.items():
                yaml.command(
                    f'{VENV}/bin/rally task report '
                    f'  --uuid {" ".join(uuids)} --html-static'
                    f'  --out rally-report.html',
                    **title(f'generate html report for {uuids}'),
                    when=f'inventory_hostname  == "{host}"')
                yaml.command(
                    f'{VENV}/bin/rally task report '
                    f'  --uuid {" ".join(uuids)} --json'
                    f'  --out rally-report.json',
                    **title(f'generate json report for {uuids}'),
                    when=f'inventory_hostname  == "{host}"')

            # Brings reports back
            for ext in ('html', 'json'):
                yaml.fetch(
                    **title(f'fetch the {ext} rally report'),
                    src=f'rally-report.{ext}', flat=True,
                    dest=(str(destination)
                          + '/{{ inventory_hostname }}-rally-report.' + ext))

    def destroy(self):
        pass

    def env_exists(self) -> bool:
        'Test whether the Rally environment exists or not'
        try:
            with elib.play_on(roles=self.rsc,
                              gather_facts=False,
                              on_error_continue=False) as yaml:
                yaml.raw(f"{VENV}/bin/rally env show '{self.env_name}'")
        except elib.errors.EnosFailedHostsError:
            logging.error('...ignoring')
            return False
        else:
            return True


def title(title: str) -> Dict[str, str]:
    "A title for ansible yaml commands"
    return {"task_name": "Rally : " + title}
