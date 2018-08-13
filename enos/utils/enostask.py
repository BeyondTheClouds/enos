# -*- coding: utf-8 -*-
from enos.utils.constants import SYMLINK_NAME
import os


def check_env(fn):
    """Decorator for an Enos Task.

    This decorator checks if an environment file exists.

    """
    def decorator(*args, **kwargs):
        # If no directory is provided, set the default one
        resultdir = kwargs.get('--env', SYMLINK_NAME) or SYMLINK_NAME
        # Check if the env file exists
        env_path = os.path.join(resultdir, 'env')
        if not os.path.isfile(env_path):
            raise Exception("The file %s does not exist." % env_path)

        # Proceeds with the function execution
        return fn(*args, **kwargs)
    return decorator
