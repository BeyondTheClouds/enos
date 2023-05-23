# -*- coding: utf-8 -*-
"Installs and run Shaker on a list of agents"
import logging
import uuid
from pathlib import Path
from typing import Dict, List

import enoslib as elib

# Docker image for Shaker
IMG = 'performa/shaker:latest'


class Shaker():
    # Resources with agents that have Shaker
    rsc: elib.Roles

    # Directory that is mount in the docker as Shaker home
    home: str

    # Authentication variables for OpenStack (as in openrc)
    _openstack_auth: Dict[str, str] = {}

    def __init__(self, agents: List[elib.Host]):
        """Deploy Shaker OpenStack on a list of agents.

        Args:
          agents: The list of agents to deploy Shaker OpenStack on.

        Reference:
          https://opendev.org/performa/shaker
        """
        self.rsc = agents
        self.home = "~/shaker_home_" + str(uuid.uuid4())
        Shaker.pull(agents)

    @staticmethod
    def pull(agents: List[elib.Host]):
        'Pulling the docker image of Shaker '
        logging.info("Pull: get docker image for Shaker")

        with elib.play_on(roles=agents,
                          gather_facts=False) as yaml:
            yaml.docker_image(
                **title(f'pulling docker image {IMG}'),
                name=IMG, source='pull', state='present')

    def deploy(self, openstack_auth: Dict[str, str], reset=False):
        'Deploying a Shaker environment'
        logging.info(f"Deploy: make shaker environment {self.home}")

        self._openstack_auth = openstack_auth.copy()

        with elib.play_on(roles=self.rsc,
                          gather_facts=False) as yaml:
            if reset:  # Reset the environment
                yaml.file(**title(f"delete HOME {self.home}"),
                          path=self.home, state="absent")

            # Create the environment
            yaml.file(**title(f"create HOME {self.home}"),
                      path=self.home, state='directory')

    def run_scenario(self, scenario: str, pattern_hosts: str = "all"):
        'Execute the Shaker `scenario`'
        logging.info(f"Running Shaker {scenario}")

        with elib.play_on(roles=self.rsc,
                          pattern_hosts=pattern_hosts,
                          gather_facts=False) as yaml:
            yaml.docker_container(
                **title(f"run {scenario} (may take a while...)"),
                name=str(uuid.uuid4()),
                image=IMG,
                state='started',
                ports=["11234:11234"],
                detach=False,
                volumes=[f"{self.home}:/artifacts"],
                env=self._openstack_auth,
                command=(
                    ' --flavor-name m1.medium'
                    ' --server-endpoint {{ network_interface_ip }}:11234'
                    f' --scenario {scenario}'))

    def backup(self, destination: Path, pattern_hosts: str = "all"):
        'Backup Shaker HOME'
        logging.info(f"Backup Shaker reports for home {self.home}")

        with elib.play_on(roles=self.rsc,
                          pattern_hosts=pattern_hosts,
                          gather_facts=False) as yaml:
            yaml.archive(
                **title(f"archive HOME {self.home}"),
                path=self.home,
                dest=self.home + '.tar.gz',
                format='gz')
            yaml.fetch(
                **title(f"fetch HOME {self.home}"),
                src=self.home + '.tar.gz',
                dest=str(destination / '{{inventory_hostname}}-shaker.tar.gz'),
                flat=True)

    def destroy(self):
        pass


def title(title: str) -> Dict[str, str]:
    "A title for an ansible yaml commands"
    return {"task_name": "Shaker : " + title}
