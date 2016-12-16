# -*- coding: utf-8 -*-
from ..provider.g5k import G5K
from constants import SYMLINK_NAME, KOLLA_REPO, KOLLA_REF
from functools import wraps

import os
import sys
import yaml
import logging


def make_env(env_path=None):
    """Loads the `env_path` environment if not `None` or makes a new one.

    An enos environment handles all specific variables of an
    experiment. This function either generates a new environment or
    loads a previous one. If the value of `env_path` is `None`, then
    this function makes a new environment and return it. If the value
    is a file path of a yaml file that represents the enos
    environment, then this function loads and returns it.

    In case of a file_path, this function also reread the
    configuration file (the reservation.yaml) and reloads it. This
    lets the user update is configuration between each phase.

    """
    env = {
        'config':      {},  # The config
        'resultdir':   '',  # Path to the result directory
        'config_file': '',  # The initial config file
        'nodes':       {},  # Roles with nodes
        'phase':       '',  # Last phase that have been run
        'user':        '',  # User id for this job
        'kolla_repo':   KOLLA_REPO,
        'kolla_branch': KOLLA_REF
    }

    if env_path:
        if os.path.isfile(env_path):
            with open(env_path, 'r') as f:
                env.update(yaml.load(f))
                logging.debug("Loaded environment %s", env_path)
        else:
            logging.error("Wrong environment file %s", env_path)
            sys.exit(1)

        # Resets the configuration of the environment
        if os.path.isfile(env['config_file']):
            with open(env['config_file'], 'r') as f:
                env['config'].update(yaml.load(f))
                logging.debug("Reloaded config %s", env['config'])

    return env


def save_env(env):
    """Saves one environment."""
    env_path = os.path.join(env['resultdir'], 'env')

    if os.path.isdir(env['resultdir']):
        with open(env_path, 'w') as f:
            yaml.dump(env, f)

def enostask(doc):
    """Decorator for a Enos Task.


    This decorator lets you define a new enos task and helps you
    manage the environment.

    """
    def decorator(fn):
        fn.__doc__ = doc

        @wraps(fn)
        def decorated(*args, **kwargs):
            # TODO: Dynamically loads the provider
            if '--provider' in kwargs:
                provider_name = kwargs['--provider']
                kwargs['provider'] = G5K()

            # Constructs the environment
            kwargs['env'] = make_env(kwargs['--env'])

            # Proceeds with the function executio
            fn(*args, **kwargs)

            # Save the environment
            save_env(env)
        return decorated
    return decorator
