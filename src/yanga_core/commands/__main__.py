"""
Helpers a pipeline step runs as its own process, with the pipeline's environment.

Not the user CLI: ``run``, ``info`` and ``features`` are ``Command`` classes the ``yanga`` front end calls directly.
"""

import sys
from argparse import ArgumentParser
from sys import argv

from py_app_dev.core.cmd_line import CommandLineHandlerBuilder
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger

from yanga_core import __version__
from yanga_core.commands.kconfig_view import KConfigViewCommand


def do_run() -> int:
    parser = ArgumentParser(prog="yanga_core_cmd", description="yanga-core CLI utilities run by pipeline steps", exit_on_error=False)
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    builder = CommandLineHandlerBuilder(parser)
    builder.add_commands([KConfigViewCommand()])
    handler = builder.create()
    return handler.run(argv[1:])


def main() -> int:
    try:
        setup_logger()
        return do_run()
    except UserNotificationException as e:
        logger.error(f"{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
