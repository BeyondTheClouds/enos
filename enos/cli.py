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

import logging
import pathlib
import sys
import textwrap
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import enos.utils.constants as C
import yaml
from docopt import docopt
from enos.utils.cli import CLI
from enos.utils.errors import (EnosFilePathError, EnosUnknownProvider,
    MissingEnvState)


def up(**kwargs):
    """\
    USAGE:
      enos up [-f CONFIG_FILE] [--force-deploy] [-t TAGS] [--pull] [-e ENV]

      Get and setup resources on the testbed.

    OPTIONS:
      -f CONFIG_FILE   Path to the configuration file describing the
                       deployment [default: ./reservation.yaml].
      --force-deploy   Force deployment.
      -t, --tags TAGS  Only run ansible tasks tagged with these values.
      --pull           Only preinstall software (e.g pull docker images).
      -e, --env ENV    Path to the environment directory (Advanced option). Enos
                       creates a directory to track the state of the
                       experiment. Use this option to link enos with a different
                       environment.
    """

    logging.debug('phase[up]: args=%s' % kwargs)
    from enos import tasks
    from enos.utils.errors import EnosFilePathError

    # Get parameters
    config_file = pathlib.Path(kwargs.get('-f', './reservation.yaml'))
    is_force_deploy = kwargs.get('--force-deploy', False)
    is_pull_only = kwargs.get('--pull', False)
    tags = kwargs.get('--tags', None)

    # Launch the *up* task
    try:
        with _elib_open(kwargs.get('--env'), new=True) as env:
            config = _load_config(config_file)
            tasks.up(env, config, is_force_deploy, is_pull_only, tags)

            CLI.print("""\
            The setup of your testbed completed successfully.  You may proceed
            with an `enos os` to deploy OpenStack on it.""")

    # Nicely handle errors for the user
    except EnosFilePathError as err:
        CLI.error(f"""\
        The path "{err.filepath}" does not point to a regular file.  Please,
        run `enos new` first or link to an existing configuration file with
        `-f` option.  See `enos help up` for more information.""")
        sys.exit(1)
    except yaml.YAMLError as err:
        error_loc = ""
        if hasattr(err, 'problem_mark'):
            loc = getattr(err, 'problem_mark')
            error_loc = f"at {loc.line+1}:{loc.column+1}"
        CLI.error(f'Syntax error in the file "{config_file}" ' + error_loc)
        sys.exit(1)
    except EnosUnknownProvider as err:
        CLI.error(str(err))
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


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
      --reconfigure    Only reconfigure the services (after a first deployment).
      --pull           Only preinstall software (e.g pull docker images).
      -t, --tags TAGS  Only run ansible tasks tagged with these values.
      -e, --env ENV    Path to the environment directory (Advanced option). Enos
                       creates a directory to track the state of the experiment.
                       Use this option to link enos with a different environment
                       [default: ./current].
    """

    logging.debug('phase[os]: args=%s' % kwargs)
    from enos import tasks

    try:
        with _elib_open(kwargs.get('--env')) as env:
            if kwargs.get('--'):
                # Directly call the kolla-ansible executable
                kolla_cmd = kwargs.get('<kolla-cmd>', [])
                tasks.kolla_ansible(env, kolla_cmd)
            else:
                # Launch the *install os* task
                is_reconfigure = kwargs.get('--reconfigure', False)
                is_pull_only = kwargs.get('--pull', False)
                tags = kwargs.get('--tags', None)

                tasks.install_os(env, is_reconfigure, is_pull_only, tags)

                CLI.print("""\
                The installation of OpenStack completed successfully.  You may
                proceed with an `enos init` to install images and setup the
                network.""")

    # Nicely handle errors for the user
    except MissingEnvState as err:
        if err.key == 'kolla-ansible':
            CLI.error("""\
            kolla-ansible could not be found in your enos environment.  Did you
            successfully run `enos up` first?""")
        else:
            CLI.critical(err)
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


def init(**kwargs):
    """\
    USAGE:
      enos init [--pull] [-e ENV]

      Initialise OpenStack with the bare necessities:
      - Install a 'member' role
      - Download and install a cirros and a debian image
      - Install default flavor (m1.tiny, ..., m1.xlarge)
      - Install default network

    OPTIONS:
      --pull         Only preinstall software (e.g pull docker images).
      -e, --env ENV  Path to the environment directory (Advanced option). Enos
                     creates a directory to track the state of the experiment.
                     Use this option to link enos with a different environment
                     [default: ./current].
    """

    logging.debug('phase[init]: args=%s' % kwargs)
    from enos import tasks

    # Get params and launch the *init* task
    try:
        with _elib_open(kwargs.get('--env')) as env:
            is_pull_only = kwargs.get('--pull', False)
            tasks.init_os(env, is_pull_only)

            os_auth = env['kolla-ansible'].globals_values['openstack_auth']
            CLI.print(f"""\
            The initialization of OpenStack completed successfully.  You may
            proceed with `source {env.env_name / 'admin-openrc'}` to then run
            the openstack CLI.  You can also access the horizon dashboard at
            http://{env['rsc']['horizon'][0].address} with user
            "{os_auth['username']}" and password "{os_auth['password']}".""")

    # Nicely handle errors for the user
    except MissingEnvState as err:
        if err.key in ['kolla-ansible', 'inventory', 'networks']:
            CLI.error(f"""\
            {err.key} could not be found in your enos environment.  Did you
            successfully run `enos up` and `enos os` first?""")
        else:
            CLI.critical(err)
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


def deploy(**kwargs):
    """\
    USAGE:
      enos deploy [-f CONFIG_FILE] [--force-deploy] [--pull] [-e ENV]

      Alias for enos up, then enos os, and finally enos init.

    OPTIONS:
      -f CONFIG_FILE  Path to the configuration file describing the
                      deployment [default: ./reservation.yaml].
      --force-deploy  Force deployment.
      --pull          Only preinstall software (e.g pull docker images).
      -e, --env ENV   Path to the environment directory (Advanced option). Enos
                      creates a directory to track the state of the
                      experiment. Use this option to link enos with a different
                      environment.
    """

    logging.debug('phase[deploy]: args=%s' % kwargs)

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
      --reset              Recreate the benchmark environment.
      --pull               Only preinstall software (e.g pull docker images).
      -e, --env ENV        Path to the environment directory (Advanced option).
                           Enos creates a directory to track the state of the
                           experiment. Use this option to link enos with a
                           different environment [default: ./current].
    """

    logging.debug('phase[bench]: args=%s' % kwargs)
    from enos import tasks
    from enos.utils.extra import seekpath
    from enos.utils.errors import EnosFilePathError

    # Get parameters
    is_reset = kwargs.get('--reset', False)
    is_pull_only = kwargs.get('--pull', False)
    workload = pathlib.Path(
        seekpath(kwargs.get('--workload', 'workload/'))).resolve()
    CLI.debug(f"Use workload directory at {workload}")

    # Launch the *bench* task
    try:
        with _elib_open(kwargs.get('--env')) as env:
            tasks.bench(env, workload, is_reset, is_pull_only)

            CLI.print("""\
            The bench phase completed.  Generated reports could be downloaded
            on your machine with `enos backup`.""")

    # Nicely handle errors for the user
    except EnosFilePathError as err:
        CLI.error(f"""\
        The path "{err.filepath}" does not point to a regular file.  Please,
        ensure to link an existing file with the `--workload`.""")
        sys.exit(1)
    except MissingEnvState as err:
        if err.key in ['kolla-ansible', 'inventory', 'networks']:
            CLI.error(f"""\
            {err.key} could not be found in your enos environment.  Did you
            successfully run `enos up` and `enos os` first?""")
        else:
            CLI.critical(err)
            raise err
        sys.exit(1)
    except yaml.YAMLError as err:
        error_loc = ""
        if hasattr(err, 'problem_mark'):
            loc = getattr(err, 'problem_mark')
            error_loc = f"at {loc.line+1}:{loc.column+1}"
        CLI.error(f'Syntax error in the file "{workload / "run.yam"}" '
                  + error_loc)
        sys.exit(1)


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

    logging.debug('phase[backup]: args=%s' % kwargs)
    from enos import tasks

    try:
        with _elib_open(kwargs.get('--env')) as env:
            # Get parameters
            backup_dir = pathlib.Path(
                kwargs.get('--backup_dir') or env.env_name).resolve()
            CLI.debug(f"Store backups at directory {backup_dir}")

            # Launch the *bench* task
            tasks.backup(env, backup_dir)

            CLI.print(f"""\
            The backup of the environment completed successfully.  Files has
            been saved at {backup_dir}.""")

    # Nicely handle errors for the user
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


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
    logging.debug('phase[new]: args=%s' % kwargs)
    from enos import tasks

    # Get parameters
    provider = kwargs['--provider']

    # Launch the *new* task
    try:
        tasks.new(provider, Path('./reservation.yaml'))

        CLI.print(f"""\
        A `reservation.yaml` file has been placed in this directory.  You are
        now ready to deploy OpenStack on {provider} with `enos deploy`.  Please
        read comments in the reservation.yaml file as well as the documentation
        on https://beyondtheclouds.github.io/enos/ for more information on
        using enos.""")

    # Nicely handle errors for the user
    except FileExistsError:
        CLI.error(f"""\
        The `reservation.yaml` file already exists in this directory.  Remove
        it before running `enos new --provider={provider}`.""")
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


def tc(**kwargs):
    """\
    USAGE:
      enos tc [--test] [--reset] [-e ENV]

      Enforce network constraints.

    OPTIONS:
      --test         Test network constraints enforcement.  This generates
                     various reports that you can get back on your machine
                     with `enos backup`.
      --reset        Reset the constraints.
      -e, --env ENV  Path to the environment directory (Advanced option). Enos
                     creates a directory to track the state of the experiment.
                     Use this option to link enos with a different environment
                     [default: ./current].

    """

    logging.debug('phase[tc]: args=%s' % kwargs)
    from enos import tasks

    # Get parameters
    validate = kwargs.get('--test', False)
    is_reset = kwargs.get('--reset', False)

    try:
        # Launch the *tc* task
        with _elib_open(kwargs.get('--env')) as env:
            tasks.tc(env, validate, is_reset)

            if validate:
                CLI.print("""\
                A test for network constraints enforcement has been done.
                Generated reports could be downloaded on your machine with
                `enos backup`.""")

    # Nicely handle errors for the user
    except MissingEnvState as err:
        if err.key == 'config':
            CLI.error(f"""\
            {err.key} could not be found in your enos environment.  Did you
            successfully run `enos up` and `enos os` first?""")
        else:
            CLI.critical(str(err))
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


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

    logging.debug('phase[info]: args=%s' % kwargs)
    import json
    import pickle

    def json_encoder(o):
        # Render pathlib.Path with str
        if isinstance(o, Path):
            return str(o.resolve())
        # Specific serializing method for some Enoslib objects
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "__dict__"):
            return o.__dict__
        if hasattr(o, "__iter__"):
            return sorted(list(o))

    # Get parameters
    output_type = kwargs.get('--out', 'json')

    # Display env
    with _elib_open(kwargs.get('--env')) as env:
        if output_type == 'json':
            print(json.dumps(env.data, default=json_encoder, indent=True))
        elif output_type == 'pickle':
            print(pickle.dumps(env.data))
        elif output_type == 'yaml':
            print(yaml.dump(env.data))
        else:
            CLI.error(f"--out doesn't support {output_type} output format")
            print(info.__doc__)


def destroy(**kwargs):
    """\
    USAGE:
      enos destroy [--include-images] [--hard] [-e ENV]

      Destroy the deployment.

    OPTIONS:
      --include-images  Remove also all the docker images.
      --hard            Destroy the resources from the testbed.
      -e, --env ENV     Path to the environment directory (Advanced option).
                        Enos creates a directory to track the state of the
                        experiment. Use this option to link enos with a
                        different environment [default: ./current].
    """

    logging.debug('phase[destroy]: args=%s' % kwargs)
    from enos import tasks

    # Get parameters
    include_images = kwargs.get('--include-images', False)

    try:
        with _elib_open(kwargs.get('--env')) as env:
            if kwargs.get('--hard', False):
                # Destroy the entire infra
                tasks.destroy_infra(env)

                CLI.print("""\
                Resources acquired from the testbed have been destroyed.  You
                may get new ones with `enos up`.""")

            else:
                # Destroy OpenStack and deployed services
                tasks.destroy_os(env, include_images)

                CLI.print("""\
                OpenStack has been destroyed from the testbed.  You may
                redeployed a new one with `enos os`.""")

    # Nicely handle errors for the user
    except MissingEnvState as err:
        if err.key in ['config', 'kolla-ansible', 'inventory']:
            CLI.error(f"""\
            {err.key} could not be found in your enos environment.  Did you run
            `enos up` and `enos os` first?""")
        else:
            CLI.critical(str(err))
        sys.exit(1)
    except Exception as e:
        CLI.critical(str(e))
        sys.exit(1)


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
                       [default: debian10-min].
    --image IMAGE      Reference image path to bake on top of it (vmong5k)
                       [default: /grid5000/virt-images/debian10-x64-base.qcow2].
    --type TYPE        Installation type of the BASE distribution
                       [default: binary].
    """

    logging.debug('phase[build]: args=%s' % kwargs)
    from enos import tasks

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

    tasks.build(provider, arguments)


def enos_help(**kwargs):
    """\
    USAGE:
      enos help [<command>]

      Show the help message for <command>
    """

    logging.debug('phase[help]: args=%s' % kwargs)

    cmd = kwargs.get("<command>")
    if cmd:  # `enos help <cmd>`
        print(textwrap.dedent(_get_cmd_func(cmd).__doc__ or ""))
    else:    # `enos help`
        print(textwrap.dedent(__doc__ or ""))


# Registry of enos commands (indexed by their name)
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

@contextmanager
def _elib_open(path: Optional[pathlib.Path], new: bool = False):
    "Open and dump enoslib env"
    from enoslib.task import get_or_create_env
    from enoslib.errors import EnosFilePathError

    try:
        # Get the environment from the file system
        env = get_or_create_env(new, path)

        # Let the user update it
        try:
            yield env

        # Save its changes on the file system
        finally:
            env.dump()

    # Nicely handle errors for the user
    except EnosFilePathError as err:
        CLI.error(f"""\
        The path "{err.filepath}" does not point to a regular file.  Please,
        ensure to link an existing file with the `--env` option or first run
        `enos up`.""")
        sys.exit(1)


def _get_cmd_func(name: str) -> Callable[..., Any]:
    """Returns the function of an enos <command> or panic gracefully

    If the name does not refer to an enos <command> that exists, this function
    print an error message and exit.

    """

    # Get the function in charge of `enos <name>`
    try:
        return _COMMANDS[name]

    # Command not found, exit with an error message
    except KeyError:
        from difflib import get_close_matches
        possibilities = get_close_matches(name, _COMMANDS.keys())

        if possibilities:
            CLI.error(f"""\
            enos command '{name}' does not exist.  The most similar command is
            '{possibilities[0]}'.""")
        else:
            CLI.error(f"""\
            enos command '{name}' does not exist.  See `enos --help` for a
            complete list of supported commands.""")

        sys.exit(1)


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
        CLI.info(f"Loaded the configuration file '{config_file}'")
        return config


def _set_logging_level(is_quiet: bool, verbose_level: int):
    "Set the root logger level"

    if is_quiet:
        logging.basicConfig(level=logging.ERROR)
        CLI.setLevel(logging.ERROR)
    elif verbose_level == 1:
        logging.basicConfig(level=logging.INFO)
        CLI.setLevel(logging.INFO)
    elif verbose_level == 2:
        logging.basicConfig(level=logging.DEBUG)
        CLI.setLevel(logging.DEBUG)


def main():
    # Parse command arguments: `enos -vv help new`
    # cli_args =
    #  {'--help': False, '--quiet': False, '--verbose': 2, '--version': False,
    #   '<command>': 'help','<args>': ['new'], }
    enos_global_args = docopt(__doc__ or "",
                              version=C.VERSION,
                              options_first=True,)
    # Set global enoslib options
    import enoslib
    # Use the "old-style" Ansible output in order to get more detailed
    # output, useful in case of errors.
    enoslib.set_config(ansible_stdout="classic")

    # Set the logging level
    _set_logging_level(
        is_quiet=enos_global_args.pop('--quiet', False),
        verbose_level=enos_global_args.pop('--verbose', 0))

    # Get the command to execute and its associated function
    enos_cmd = enos_global_args.pop('<command>')
    enos_cmd_func = _get_cmd_func(enos_cmd)

    # Parse `enos <command>` arguments, and execute it
    enos_cmd_args = docopt(doc=textwrap.dedent(enos_cmd_func.__doc__ or ""),
                           argv=[enos_cmd] + enos_global_args['<args>'])
    enos_cmd_func(**enos_cmd_args)
