# -*- coding: utf-8 -*-
"""Enos: Monitor and test your OpenStack.

usage: enos <command> [<args> ...] [-e ENV|--env=ENV]
            [-h|--help] [-v|--version] [-s|--silent|--vv]

General options:
  -e ENV --env=ENV  Path to the environment directory. You should
                    use this option when you want to link to a specific
                    experiment. Not specifying this value will
                    discard the loading of the environment (it
                    makes sense for `up`).
  -h --help         Show this help message.
  -s --silent       Quiet mode.
  -v --version      Show version number.
  -vv               Verbose mode.

Commands:
  new            Print a reservation.yaml example
  up             Get resources and install the docker registry.
  os             Run kolla and install OpenStack.
  init           Initialise OpenStack with the bare necessities.
  bench          Run Rally/Shaker on this OpenStack.
  backup         Backup the environment
  ssh-tunnel     Print configuration for port forwarding with horizon.
  tc             Enforce network constraints
  info           Show information of the actual deployment.
  destroy        Destroy the deployment and optionally the related resources.
  deploy         Shortcut for enos up, then enos os and enos config.
  build          Build a reference image for later deployment.
  help           Show this help message.


See 'enos <command> --help' for more information on a specific
command.

"""

import logging
import textwrap
from os import path
from pathlib import Path
from docopt import docopt
import yaml

import enos.tasks as tt
import enos.task as t
import enos.utils.constants as C
from enos.utils.errors import EnosFilePathError

logger = logging.getLogger(__name__)


def load_config(config_file):
    config = {}
    if path.isfile(config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            logging.info("Reloaded configuration file %s", config_file)
            logging.debug("Configuration is %s", config)
    else:
        raise EnosFilePathError(
            config_file, "Configuration file %s does not exist" % config_file)

    return config_file, config


def up(**kwargs):
    """
    usage: enos up  [-e ENV|--env=ENV][-f CONFIG_FILE] [--force-deploy]
                    [-t TAGS|--tags=TAGS] [-s|--silent|-vv]

    Get resources and install the docker registry.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link to a specific
                         experiment. Do not specify it in other cases.
    -f CONFIG_FILE       Path to the configuration file describing the
                         deployment [default: ./reservation.yaml].
    -h --help            Show this help message.
    --force-deploy       Force deployment [default: False].
    --pull               Only preinstall software (e.g pull docker images)
                         [default: False].
    -s --silent          Quiet mode.
    -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
    -vv                  Verbose mode.

    """
    logger.debug(kwargs)
    config_file, config = load_config(kwargs['-f'])
    t.up(config, config_file=config_file, **kwargs)


def os(**kwargs):
    """Usage:
      enos os [-e ENV|--env=ENV] [--reconfigure] [-t TAGS|--tags=TAGS]
              [-s|--silent|-vv]
      enos os [-e ENV|--env=ENV] [-s|--silent|-vv] -- <kolla-cmd> ...

    Install OpenStack with kolla-ansible.

    The second command falls back on kolla to run arbitrary commands, e.g.,
    `enos os -- prechecks`, see `enos os -- -help` for an exhaustive list of
    supported commands.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    --reconfigure        Reconfigure the services after a deployment.
    --pull               Only preinstall software (e.g pull docker images)
                         [default: False].
    -s --silent          Quiet mode.
    -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
    -vv                  Verbose mode.

    """
    logger.debug(kwargs)
    t.install_os(**kwargs)


def init(**kwargs):
    """
    usage: enos init [-e ENV|--env=ENV] [-s|--silent|-vv] [--pull]

    Initialise OpenStack with the bare necessities:
    - Install a 'member' role
    - Download and install a cirros image
    - Install default flavor (m1.tiny, ..., m1.xlarge)
    - Install default network

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    --pull               Only preinstall software (e.g pull docker images)
                         [default: False].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    t.init_os(**kwargs)


def bench(**kwargs):
    """
    usage: enos bench [-e ENV|--env=ENV] [-s|--silent|-vv]
        [--workload=WORKLOAD] [--pull] [--reset]

    Run Rally/Shaker on this OpenStack.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    --workload=WORKLOAD  Path to the workload directory.
                         This directory must contain a run.yml file
                         that contains the description of the different
                         scenarios to launch [default: workload/].
    --reset              Force the creation of benchmark environment.

    --pull               Only preinstall software (e.g pull docker images)
                         [default: False].
    """
    logger.debug(kwargs)
    t.bench(**kwargs)


def backup(**kwargs):
    """
    usage: enos backup [--backup_dir=BACKUP_DIR] [-e ENV|--env=ENV]
                    [-s|--silent|-vv]

    Backup the environment

    Options:
    --backup_dir=BACKUP_DIR  Backup directory.
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    t.backup(**kwargs)


def new(**kwargs):
    """
    usage: enos new [--provider=TESTBED] [-s|--silent|-vv]

    Create a basic reservation.yaml file in the current directory.

    Options:
    --provider=TESTBED  Targeted testbed. One of g5k, vagrant:virtualbox,
                        vagrant:libvirt, chameleonkvm, chameleonbaremetal,
                        openstack, vmong5k, static [default: g5k].
    -s --silent         Quiet mode.
    -vv                 Verbose mode.
    """
    logger.debug(kwargs)
    provider = kwargs['--provider']

    try:
        tt.new(provider, Path('./reservation.yaml'))
        logger.info(textwrap.fill(
            'A `reservation.yaml` file has been placed in this directory.  '
            f'You are now ready to deploy OpenStack on {provider} with '
            '`enos deploy`.  Please read comments in the reservation.yaml '
            'as well as the documentation on '
            f'https://beyondtheclouds.github.io/enos/ '
            'for more information on using enos.'))
    except FileExistsError:
        logger.error(textwrap.fill(
            'The `reservation.yaml` file already exists in this directory.  '
            f'Remove it before running `enos new --provider={provider}`.'))


def tc(**kwargs):
    """
    usage: enos tc [-e ENV|--env=ENV] [--test] [--reset] [-s|--silent|-vv]

    Enforce network constraints

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    --test               Test the rules by generating various reports.
    --reset              Reset the constraints.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    t.tc(**kwargs)


def info(**kwargs):
    """
    usage: enos info [-e ENV|--env=ENV] [--out={json,pickle,yaml}]

    Show information of the `ENV` deployment.

    Options:

    -e ENV --env=ENV         Path to the environment directory. You should use
                             this option when you want to link a
                             specific experiment [default: current].

    --out {json,pickle,yaml} Output the result in either json, pickle or
                             yaml format [default: json].
    """
    logger.debug(kwargs)
    t.info(**kwargs)


def destroy(**kwargs):
    """
    usage: enos destroy [-e ENV|--env=ENV] [-s|--silent|-vv] [--hard]
                        [--include-images]

    Destroy the deployment.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    --hard               Destroy the underlying resources as well.
    --include-images     Remove also all the docker images.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    t.destroy(**kwargs)


def deploy(**kwargs):
    """
    usage: enos deploy [-e ENV|--env=ENV] [-f CONFIG_FILE] [--force-deploy]
                    [--pull] [-s|--silent|-vv]

    Shortcut for enos up, then enos os, and finally enos config.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment.
    -f CONFIG_FILE       Path to the configuration file describing the
                         deployment [default: ./reservation.yaml].
    --force-deploy       Force deployment [default: False].
    --pull               Only preinstall software (e.g pull docker images)
                         [default: False].
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    config_file, config = load_config(kwargs['-f'])
    t.deploy(config, config_file=config_file, **kwargs)


def build(**kwargs):
    """
    usage: enos build <provider> [options]

    Build a reference image for later deployment.

    The built is done for a given <provider> (vagrant, g5k or vmong5k). Some
    options apply only to some providers, see below.

    Options:

    --backend BACKEND  Virtualization backend (vagrant).
                       [default: virtualbox].
    --base BASE        Base distribution for deployed virtual machines
                       [default: centos].
    --box BOX          Reference box for host virtual machines (vagrant)
                       [default: generic/debian10].
    --cluster CLUSTER  Cluster where the image is built (g5k and vmong5k)
                       [default: parasilo].
    --directory DIR    Directory in which the image will be baked (vmong5k)
                       [default: ~/.enos].
    --environment ENV  Reference environment for deployment (g5k)
                       [default: debian10-x64-min].
    --image IMAGE      Reference image path to bake on top of it (vmong5k)
                       [default: /grid5000/virt-images/debian10-x64-base.qcow2].
    --type TYPE        Installation type of the BASE distribution
                       [default: binary].

    -h --help          Show this help message.
    -s --silent        Quiet mode.
    -vv                Verbose mode.

    """

    logger.debug(kwargs)
    provider = kwargs.pop('<provider>')
    arguments = {}
    if '--backend' in kwargs:
        arguments['backend'] = kwargs['--backend']
    if '--base' in kwargs:
        arguments['base'] = kwargs['--base']
    if '--box' in kwargs:
        arguments['box'] = kwargs['--box']
    if '--cluster' in kwargs:
        arguments['cluster'] = kwargs['--cluster']
    if '--directory' in kwargs:
        arguments['directory'] = kwargs['--directory']
    if '--environment' in kwargs:
        arguments['environment'] = kwargs['--environment']
    if '--image' in kwargs:
        arguments['image'] = kwargs['--image']
    if '--type' in kwargs:
        arguments['distribution'] = kwargs['--type']
    t.build(provider, **arguments)


def _configure_logging(args):
    if '-vv' in args['<args>']:
        logging.basicConfig(level=logging.DEBUG)
    elif '-s' in args['<args>']:
        logging.basicConfig(level=logging.ERROR)
        args['<args>'].remove('-s')
    elif '--silent' in args['<args>']:
        logging.basicConfig(level=logging.ERROR)
        args['<args>'].remove('--silent')
    else:
        logging.basicConfig(level=logging.INFO)


def pushtask(ts, f):
    ts.update({f.__name__: f})


def main():
    args = docopt(__doc__,
                  version=C.VERSION,
                  options_first=True)

    _configure_logging(args)
    argv = [args['<command>']] + args['<args>']

    if argv == ['help']:
        print(__doc__)
        return

    enostasks = {}
    pushtask(enostasks, backup)
    pushtask(enostasks, bench)
    pushtask(enostasks, deploy)
    pushtask(enostasks, destroy)
    pushtask(enostasks, info)
    pushtask(enostasks, init)
    pushtask(enostasks, os)
    pushtask(enostasks, new)
    pushtask(enostasks, tc)
    pushtask(enostasks, up)
    pushtask(enostasks, build)

    task = enostasks[args['<command>']]
    task(**docopt(task.__doc__, argv=argv))
