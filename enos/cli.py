# -*- coding: utf-8 -*-
"""\
Enos: Deploy and test your OpenStack.

USAGE:
  enos [-h] [-q|-v|-vv] [-V] <command> [<args> ...]

ARGUMENTS:
  <command>      The command to execute.
  <args>         The arguments of the command.

GLOBAL OPTIONS:
  -h --help      Show this help message.
  -q --quiet     Do not output any message.
  -v --verbose   Increase the verbosity of messages: '-v' for verbose output,
                 '-vv' for debug.
  -V --version   Show version number.

COMMANDS:
  new            Create a reservation.yaml file in the current directory.
  up             Get and setup resources on the testbed.
  os             Install OpenStack.
  init           Initialise OpenStack with the bare necessities.
  deploy         Alias for enos up, then enos os and finally enos init.
  bench          Run Rally/Shaker on this OpenStack.
  backup         Backup OpenStack/bench logs.
  tc             Enforce network constraints
  info           Show information of the actual deployment.
  destroy        Destroy the deployment and optionally the related resources.
  build          Build a reference image for later deployment.
  help           Show this help message.

See 'enos help <command>' for more information on a specific command.
"""

import sys
import logging
import pathlib
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict

import enos.utils.constants as C
import yaml
from docopt import docopt
from enos.utils.errors import EnosFilePathError, EnosUnknownProvider


LOGGER = logging.getLogger(__name__)


def up(**kwargs):
    """\
    USAGE:
      enos up [-f CONFIG_FILE] [--force-deploy] [-t TAGS] [--pull] [-e ENV]

      Get and setup resources on the testbed.

    OPTIONS:
      -f CONFIG_FILE   Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
      --force-deploy   Force deployment [default: False].
      -t, --tags TAGS  Only run ansible tasks tagged with these values.
      --pull           Only preinstall software (e.g pull docker images)
                       [default: False].
      -e, --env ENV    Path to the environment directory (Advanced option). Enos
                       creates a directory to track the state of the
                       experiment. Use this option to link enos with a different
                       environment.
    """

    LOGGER.debug('phase[up]: args=%s' % kwargs)
    import enos.tasks as tasks

    # Get parameters
    config_file = pathlib.Path(kwargs.get('-f', './reservation.yaml'))
    is_force_deploy = kwargs.get('--force-deploy', False)
    is_pull_only = kwargs.get('--pull', False)
    tags = kwargs.get('--tags', None)

    # Launch the *up* task
    try:
        config = _load_config(config_file)
        tasks.up(config, is_force_deploy, is_pull_only, tags)

    # Display nice error messages for the user
    except EnosFilePathError as err:
        LOGGER.error(textwrap.fill(
            f'The path "{err.filepath}" does not point to a regular file. '
            'Please, ensure to link an existing file with the `-f` option '
            'or first create a "reservation.yaml" file with `enos new`.'))
    except yaml.YAMLError as err:
        error_loc = ""
        if hasattr(err, 'problem_mark'):
            loc = getattr(err, 'problem_mark')
            error_loc = f"at {loc.line+1}:{loc.column+1}"

        LOGGER.error(f'Syntax error in the file {config_file} '
                     + error_loc)
    except EnosUnknownProvider as err:
        LOGGER.error(textwrap.fill(str(err)))


def os(**kwargs):
    """\
    USAGE:
      enos os [--reconfigure] [-t TAGS] [--pull] [-e ENV]
      enos os [-e ENV] -- <kolla-cmd> ...

      Install OpenStack with kolla-ansible.

      The second command falls back on kolla-ansible to run arbitrary commands,
      e.g., `enos os -- prechecks`. See `enos os -- --help` for an exhaustive
      list of supported commands.

    OPTIONS:
      --reconfigure    Reconfigure the services after a deployment.
      -t, --tags TAGS  Only run ansible tasks tagged with these values.
      --pull           Only preinstall software (e.g pull docker images)
                       [default: False].
      -e, --env ENV    Path to the environment directory (Advanced option). Enos
                       creates a directory to track the state of the experiment.
                       Use this option to link enos with a different environment
                       [default: ./current].
    """

    LOGGER.debug('phase[os]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.install_os(**kwargs)


def init(**kwargs):
    """\
    USAGE:
      enos init [--pull] [-e ENV]

      Initialise OpenStack with the bare necessities:
      - Install a 'member' role
      - Download and install a cirros image
      - Install default flavor (m1.tiny, ..., m1.xlarge)
      - Install default network

    OPTIONS:
      --pull         Only preinstall software (e.g pull docker images)
                     [default: False].
      -e, --env ENV  Path to the environment directory (Advanced option). Enos
                     creates a directory to track the state of the experiment.
                     Use this option to link enos with a different environment
                     [default: ./current].
    """

    LOGGER.debug('phase[init]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.init_os(**kwargs)


def deploy(**kwargs):
    """\
    USAGE:
      enos deploy [-f CONFIG_FILE] [--force-deploy] [--pull] [-e ENV]

      Alias for enos up, then enos os, and finally enos init.

    OPTIONS:
      -f CONFIG_FILE  Path to the configuration file describing the
                      deployment [default: ./reservation.yaml].
      --force-deploy  Force deployment [default: False].
      --pull          Only preinstall software (e.g pull docker images)
                      [default: False].
      -e, --env ENV   Path to the environment directory (Advanced option). Enos
                      creates a directory to track the state of the
                      experiment. Use this option to link enos with a different
                      environment.
    """

    LOGGER.debug('phase[deploy]: args=%s' % kwargs)

    # --tags cannot be provided in 'deploy' but is mandatory for
    # 'up'. Similarly, --reconfigure cannot be provided in 'deploy' but is
    # mandatory for 'os'.
    kwargs['--tags'] = None
    kwargs['--reconfigure'] = False

    up(**kwargs)

    # If the user doesn't specify an experiment, then set the ENV directory to
    # the default one.
    if not kwargs['--env']:
        kwargs['--env'] = C.SYMLINK_NAME

    os(**kwargs)
    init(**kwargs)


def bench(**kwargs):
    """\
    USAGE:
      enos bench [--workload=WORKLOAD] [--reset] [--pull] [-e ENV]

      Run Rally/Shaker on this OpenStack.

    OPTIONS:
      --workload=WORKLOAD  Path to the workload directory.
                           This directory must contain a run.yml file
                           that contains the description of the different
                           scenarios to launch [default: workload/].
      --reset              Force the creation of benchmark environment.
      --pull               Only preinstall software (e.g pull docker images)
                           [default: False].
      -e, --env ENV        Path to the environment directory (Advanced option).
                           Enos creates a directory to track the state of the
                           experiment. Use this option to link enos with a
                           different environment [default: ./current].
    """

    LOGGER.debug('phase[bench]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.bench(**kwargs)


def backup(**kwargs):
    """\
    USAGE:
      enos backup [--backup_dir=BACKUP_DIR] [-e ENV]

      Backup the environment.

    OPTIONS:
      --backup_dir=BACKUP_DIR  Backup directory.
      -e, --env ENV            Path to the environment directory (Advanced
                               option). Enos creates a directory to track the
                               state of the experiment. Use this option to
                               link enos with a different environment
                               [default: ./current].
    """

    LOGGER.debug('phase[backup]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.backup(**kwargs)


def new(**kwargs):
    """\
    USAGE:
      enos new [-p TESTBED]

      Create a basic reservation.yaml file in the current directory.

    OPTIONS:
      -p, --provider TESTBED  Targeted testbed. One of g5k, vagrant:virtualbox,
                              vagrant:libvirt, chameleonkvm, chameleonbaremetal,
                              openstack, vmong5k, static [default: g5k].
    """
    LOGGER.debug('phase[new]: args=%s' % kwargs)
    import enos.tasks as tasks

    # Get parameters
    provider = kwargs['--provider']

    # Launch the *new* task
    try:
        tasks.new(provider, Path('./reservation.yaml'))
        LOGGER.info(textwrap.fill(
            'A `reservation.yaml` file has been placed in this directory.  '
            f'You are now ready to deploy OpenStack on {provider} with '
            '`enos deploy`.  Please read comments in the reservation.yaml '
            'as well as the documentation on '
            f'https://beyondtheclouds.github.io/enos/ '
            'for more information on using enos.'))
    except FileExistsError:
        LOGGER.error(textwrap.fill(
            'The `reservation.yaml` file already exists in this directory.  '
            f'Remove it before running `enos new --provider={provider}`.'))


def tc(**kwargs):
    """\
    USAGE:
      enos tc [--test] [--reset] [-e ENV]

      Enforce network constraints.

    OPTIONS:
      --test         Test rule enforcement.  This generates various reports that
                     you can get back on your machine with `enos backup`.
      --reset        Reset the constraints.
      -e, --env ENV  Path to the environment directory (Advanced option). Enos
                     creates a directory to track the state of the experiment.
                     Use this option to link enos with a different environment
                     [default: ./current].
    """

    LOGGER.debug('phase[tc]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.tc(**kwargs)


def info(**kwargs):
    """\
    USAGE:
      enos info [-o {json,yaml,pickle}] [-e ENV]

      Show information of the `ENV` deployment.

    OPTIONS:
      -o, --out FORMAT  Output the result in either json, pickle or yaml
                        FORMAT [default: json].
      -e, --env ENV     Path to the environment directory (Advanced option).
                        Enos creates a directory to track the state of the
                        experiment. Use this option to link enos with a
                        different environment [default: ./current].
    """

    LOGGER.debug('phase[info]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.info(**kwargs)


def destroy(**kwargs):
    """\
    USAGE:
      enos destroy [--include-images] [--hard] [-e ENV]

      Destroy the deployment.

    OPTIONS:
      --include-images  Remove also all the docker images.
      --hard            Destroy the underlying resources as well.
      -e, --env ENV     Path to the environment directory (Advanced option).
                        Enos creates a directory to track the state of the
                        experiment. Use this option to link enos with a
                        different environment [default: ./current].
    """

    LOGGER.debug('phase[destroy]: args=%s' % kwargs)
    import enos.task as tasks

    tasks.destroy(**kwargs)


def build(**kwargs):
    """\
    USAGE:
      enos build <provider> [options]

      Build a reference image for later deployment.

      The built is done for a given <provider> (vagrant, g5k or vmong5k). Some
      options apply only to some providers, see below.

    OPTIONS:
    --backend BACKEND  Virtualization backend (vagrant).
                       [default: virtualbox].
    --base BASE        Base distribution for deployed virtual machines
                       [default: centos].
    --box BOX          Reference box for host virtual machines (vagrant)
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
    """

    LOGGER.debug('phase[build]: args=%s' % kwargs)
    import enos.task as tasks

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
    tasks.build(provider, **arguments)


def enos_help(**kwargs):
    "USAGE: enos help [<command>]"

    LOGGER.debug('phase[help]: args=%s' % kwargs)

    cmd = kwargs.get("<command>")
    if cmd:  # `enos help <cmd>`
        print(textwrap.dedent(get_cmd_func(cmd).__doc__))
    else:    # `enos help`
        print(textwrap.dedent(__doc__))


# Register enos commands' name and their function
_COMMANDS = {
    "new": new,
    "up": up,
    "os": os,
    "init": init,
    "deploy": deploy,
    "bench": bench,
    "backup": backup,
    "tc": tc,
    "info": info,
    "destroy": destroy,
    "build": build,
    "help": enos_help,
}


# utils

def _load_config(config_file: Path) -> Dict[str, Any]:
    "Load the yaml `config_file`"

    # Ensure `config_file` points to a file
    if not config_file.is_file():
        raise EnosFilePathError(
            config_file,
            f'Configuration file {config_file} does not exist')

    # Parse it
    with open(config_file, 'r') as yaml_file:
        config = yaml.safe_load(yaml_file)
        LOGGER.info(f"Loaded configuration file {config_file}")
        return config


def _set_logging_level(is_quiet: bool, verbose_level: int):
    "Set the root logger level"

    if is_quiet:
        logging.basicConfig(level=logging.ERROR)
    elif verbose_level == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbose_level == 2:
        logging.basicConfig(level=logging.DEBUG)


def get_cmd_func(name: str) -> Callable[..., Any]:
    """Returns the function of an enos <command> or panic gracefully

    If the name does not refer to an enos <command> that exits, this function
    print an error message and exit.
    """

    try:
        return _COMMANDS[name]
    except KeyError:
        cmd_names = ", ".join(_COMMANDS.keys())
        LOGGER.error(textwrap.fill(
            f"enos command '{name}' does not exist. "
            f"Use one of these commands instead: {cmd_names}."))
        sys.exit(1)


def main():
    # Parse command arguments: `enos -vv help new`
    # cli_args =
    #  {'--help': False, '--quiet': False, '--verbose': 2, '--version': False,
    #   '<command>': 'help','<args>': ['new'], }
    enos_global_args = docopt(__doc__, version=C.VERSION, options_first=True,)

    # Set the logging level
    _set_logging_level(
        is_quiet=enos_global_args.pop('--quiet', False),
        verbose_level=enos_global_args.pop('--verbose', 0))

    # Get the command to execute and its associated function
    enos_cmd = enos_global_args.pop('<command>')
    enos_cmd_func = get_cmd_func(enos_cmd)

    # Parse `enos <command>` arguments, and execute it
    enos_cmd_args = docopt(doc=textwrap.dedent(enos_cmd_func.__doc__),
                           argv=[enos_cmd] + enos_global_args['<args>'])
    enos_cmd_func(**enos_cmd_args)
