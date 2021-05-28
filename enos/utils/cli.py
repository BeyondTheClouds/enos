# -*- coding: utf-8 -*-
'''Manage CLI output.

This file offers the `CLI` object to display information to the user at the CLI
level.  CLI is implemented as a python logger, hence, we can control the level
of information to display to the user with well known `debug`, `info`,
`warning`, `error` and `critical` methods.  We also add a new logging level
named `CLI_LEVEL`.  CLI_LEVEL is a logging level between INFO and WARNING to
print normal console output to the user in the CLI.  To display information at
the `CLI_LEVEL` use the method `CLI.print`.

With a logger, the output can be easily disable by setting the log level to
something upper to the `CLI` level.  This is handy to implement the `--quiet`
option that should not display information on the standard output (stdout).

Outputs from the CLI logger also come with nice shinny colors ✨

'''
import logging
import sys
import textwrap
from typing import cast


# CLI_LEVEL is a logging level between INFO and WARNING to display console
# output to the user in the CLI, but that can be disable by setting the
# logging level to something upper.
_CLI_LEVEL = logging.INFO + 5
logging.addLevelName(_CLI_LEVEL, 'CLI')


class _CLI(logging.Logger):
    'The CLI logger with the CLI.print() method'

    def _init__(self, name):
        super(_CLI, self).__init__(name)

    def print(self, message, *args, **kwargs):
        'Output a message at the CLI_LEVEL'

        self.log(_CLI_LEVEL, message, *args, **kwargs)


# Instantiate the CLI output formatter
logging.setLoggerClass(_CLI)
CLI = cast(_CLI, logging.getLogger('enos-cli'))

# Do not pass events to other handler
CLI.propagate = False

# Defaults print at CLI_LEVEL
CLI.setLevel(_CLI_LEVEL)


# ✨ Pimp with colors ✨


# ANSI color escape code
# https://en.wikipedia.org/wiki/ANSI_escape_code#3-bit_and_4-bit
BLACK = "\033[30m"
RED = "\033[31m"
BOLD_RED = "\033[1;31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
BOLD_MAGENTA = "\033[1;35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
RESET = "\033[0m"


# See https://stackoverflow.com/a/56944256
class ColorFormatter(logging.Formatter):
    "Logging Formatter to add colors to debug, info, warning, errors..."

    log_format = "%(message)s\n(%(levelname)s %(filename)s:%(lineno)d)"

    # Follow the same color definition than ansible
    level_formats = {
        logging.DEBUG: CYAN + log_format + RESET,
        logging.INFO: BLUE + log_format + RESET,
        _CLI_LEVEL: GREEN + "%(message)s" + RESET,
        logging.WARNING: BOLD_MAGENTA + log_format + RESET,
        logging.ERROR: RED + log_format + RESET,
        logging.CRITICAL: BOLD_RED + log_format + RESET
    }

    def format(self, record):
        log_fmt = self.level_formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        error_msg = record.msg

        # Since this formatter is for CLI output only we wrap the displayed
        # text to 78 chars.  This partially breaks grep for search but this is
        # not your normal logger, but rather a dedicated one for the CLI.
        record.msg = textwrap.fill(textwrap.dedent(error_msg), width=78)
        return formatter.format(record)


ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(ColorFormatter())
CLI.addHandler(ch)
