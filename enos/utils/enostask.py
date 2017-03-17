# -*- coding: utf-8 -*-
from constants import SYMLINK_NAME
from functools import wraps

import os
import yaml
import logging


def make_env(resultdir=None):
    """Loads the env from `resultdir` if not `None` or makes a new one.

    An Enos environment handles all specific variables of an
    experiment. This function either generates a new environment or
    loads a previous one. If the value of `resultdir` is `None`, then
    this function makes a new environment and return it. If the value
    is a directory path that contains an Enos environment, then this function
    loads and returns it.

    In case of a directory path, this function also rereads the
    configuration file (the reservation.yaml) and reloads it. This
    lets the user update his configuration between each phase.

    """
    env = {
        'config':      {},  # The config
        'resultdir':   '',  # Path to the result directory
        'config_file': '',  # The initial config file
        'nodes':       {},  # Roles with nodes
        'phase':       '',  # Last phase that have been run
        'user':        ''   # User id for this job
    }

    if resultdir:
        env_path = os.path.join(resultdir, 'env')
        if os.path.isfile(env_path):
            with open(env_path, 'r') as f:
                env.update(yaml.load(f))
                logging.debug("Loaded environment %s", env_path)

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
            # Constructs the environment
            kwargs['env'] = make_env(kwargs['--env'])
            # If no directory is provided, set the default one
            if '--env' not in kwargs:
                kwargs['env']['resultdir'] = SYMLINK_NAME

            # Proceeds with the function execution
            fn(*args, **kwargs)

            # Save the environment
            save_env(kwargs['env'])
        return decorated
    return decorator
