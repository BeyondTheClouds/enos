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
  bench          Run rally on this OpenStack.
  backup         Backup the environment
  ssh-tunnel     Print configuration for port forwarding with horizon.
  tc             Enforce network constraints
  info           Show information of the actual deployment.
  destroy        Destroy the deployment and optionally the related resources.
  deploy         Shortcut for enos up, then enos os and enos config.
  kolla          Runs arbitrary kolla command on nodes


See 'enos <command> --help' for more information on a specific
command.

"""

import logging
from docopt import docopt
import enos.task as t

logger = logging.getLogger(__name__)
VERSION = "__enoslib__"


def up(**kwargs):
    """
    usage: enos up  <provider> [-e ENV|--env=ENV][-f CONFIG_PATH] [--force-deploy]
                    [-t TAGS|--tags=TAGS] [-s|--silent|-vv]

    Get resources and install the docker registry.

    Options:
    provider             Provider to use (e.g vagrant, g5k)
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link to a specific
                         experiment. Do not specify it in other cases.
    -f CONFIG_PATH       Path to the configuration file describing the
                         deployment [default: ./reservation.yaml].
    -h --help            Show this help message.
    --force-deploy       Force deployment [default: False].
    -s --silent          Quiet mode.
    -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
    -vv                  Verbose mode.

    """
    logger.debug(kwargs)
    provider = kwargs.pop('<provider>')
    t.up(provider, **kwargs)


def os(**kwargs):
    """
    usage: enos os [-e ENV|--env=ENV] [--reconfigure] [-t TAGS|--tags=TAGS]
                [-s|--silent|-vv]

    Run kolla and install OpenStack.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    --reconfigure        Reconfigure the services after a deployment.
    -s --silent          Quiet mode.
    -t TAGS --tags=TAGS  Only run ansible tasks tagged with these values.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    t.install_os(**kwargs)


def init(**kwargs):
    """
    usage: enos init [-e ENV|--env=ENV] [-s|--silent|-vv]

    Initialise OpenStack with the bare necessities:
    - Install a 'member' role
    - Download and install a cirros image
    - Install default flavor (m1.tiny, ..., m1.xlarge)
    - Install default network

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    pass




def bench(**kwargs):
    """
    usage: enos bench [-e ENV|--env=ENV] [-s|--silent|-vv] [--workload=WORKLOAD]
        [--reset]

    Run rally on this OpenStack.

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
    """
    logger.debug(kwargs)
    pass


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
    pass



def new(**kwargs):
    """
    usage: enos new [-e ENV|--env=ENV] [-s|--silent|-vv]

    Print reservation example, to be manually edited and customized:

    enos new > reservation.yaml

    Options:
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    pass


def tc(**kwargs):
    """
    usage: enos tc [-e ENV|--env=ENV] [--test] [-s|--silent|-vv]

    Enforce network constraints

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    --test               Test the rules by generating various reports.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    pass


def info(**kwargs):
    """
    usage: enos info [-e ENV|--env=ENV] [--out={json,pickle,yaml}]

    Show information of the `ENV` deployment.

    Options:

    -e ENV --env=ENV         Path to the environment directory. You should use
                             this option when you want to link a
                             specific experiment [default: current].

    --out {json,pickle,yaml} Output the result in either json, pickle or
                             yaml format.
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
    pass


def deploy(**kwargs):
    """
    usage: enos deploy <provider> [-e ENV|--env=ENV] [-f CONFIG_PATH] [--force-deploy]
                    [-s|--silent|-vv]

    Shortcut for enos up, then enos os, and finally enos config.

    Options:
    provider             Provider to use (e.g vagrant, g5k)
    -e ENV --env=ENV     Path to the environment directory. You should
                         use this option when you want to link a specific
                         experiment.
    -f CONFIG_PATH       Path to the configuration file describing the
                         deployment [default: ./reservation.yaml].
    --force-deploy       Force deployment [default: False].
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    """
    logger.debug(kwargs)
    pass


def kolla(**kwargs):
    """
    usage: enos kolla [-e ENV|--env=ENV] [-s|--silent|-vv] -- <command>...

    Run arbitrary Kolla command.

    Options:
    -e ENV --env=ENV     Path to the environment directory. You should
                        use this option when you want to link a specific
                        experiment [default: current].
    -h --help            Show this help message.
    -s --silent          Quiet mode.
    -vv                  Verbose mode.
    command              Kolla command (e.g prechecks, checks, pull)
    """
    logger.debug(kwargs)
    pass


def _configure_logging(args):
    if '-vv' in args['<args>']:
        logging.basicConfig(level=logging.DEBUG)
        args['<args>'].remove('-vv')
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
                  version=VERSION,
                  options_first=True)

    _configure_logging(args)
    argv = [args['<command>']] + args['<args>']

    enostasks = {}
    pushtask(enostasks, backup)
    pushtask(enostasks, bench)
    pushtask(enostasks, deploy)
    pushtask(enostasks, destroy)
    pushtask(enostasks, kolla)
    pushtask(enostasks, info)
    pushtask(enostasks, init)
    pushtask(enostasks, os)
    pushtask(enostasks, new)
    pushtask(enostasks, tc)
    pushtask(enostasks, up)

    task = enostasks[args['<command>']]
    task(**docopt(task.__doc__, argv=argv))

