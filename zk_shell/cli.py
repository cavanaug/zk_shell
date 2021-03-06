""" entry point for CLI wrapper """

from __future__ import print_function

import argparse
from collections import namedtuple
import logging
import signal
import sys


from . import __version__
from .shell import Shell

try:
    raw_input
except NameError:
    raw_input = input


class CLIParams(
        namedtuple("CLIParams",
                   "connect_timeout run_once run_from_stdin sync_connect hosts readonly")):
    """
    This defines the running params for a CLI() object. If you'd like to do parameters processing
    from some other point you'll need to fill up an instance of this class and pass it to
    CLI()(), i.e.:

    ```
      params = parmas_from_argv()
      clip = CLIParams(params.connect_timeout, ...)
      cli = CLI()
      cli(clip)
    ```

    """
    pass


def get_params():
    """ get the cmdline params """
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect-timeout",
                        type=int,
                        default=10,
                        help="ZK connect timeout")
    parser.add_argument("--run-once",
                        type=str,
                        default="",
                        help="Run a command non-interactively and exit")
    parser.add_argument("--run-from-stdin",
                        action="store_true",
                        default=False,
                        help="Read cmds from stdin, run them and exit")
    parser.add_argument("--sync-connect",
                        action="store_true",
                        default=False,
                        help="Connect syncronously.")
    parser.add_argument("--readonly",
                        action="store_true",
                        default=False,
                        help="Enable readonly.")
    parser.add_argument("hosts",
                        nargs="*",
                        help="ZK hosts to connect")
    params = parser.parse_args()
    return CLIParams(
        params.connect_timeout,
        params.run_once,
        params.run_from_stdin,
        params.sync_connect,
        params.hosts,
        params.readonly)


class StateTransition(Exception):
    """ raised when the connection changed state """
    pass


def sigusr_handler(*_):
    """ handler for SIGUSR2 """
    raise StateTransition()


def set_unbuffered_mode():
    """
    make output unbuffered
    """
    class Unbuffered(object):
        def __init__(self, stream):
            self.stream = stream
        def write(self, data):
            self.stream.write(data)
            self.stream.flush()
        def __getattr__(self, attr):
            return getattr(self.stream, attr)

    sys.stdout = Unbuffered(sys.stdout)


class CLI(object):
    """ the REPL """

    def __call__(self, params=None):
        """ parse params & loop forever """
        logging.basicConfig(level=logging.ERROR)

        if params is None:
            params = get_params()

        interactive = params.run_once == "" and not params.run_from_stdin
        async = False if params.sync_connect or not interactive else True

        if not interactive:
            set_unbuffered_mode()

        shell = Shell(params.hosts,
                      params.connect_timeout,
                      setup_readline=interactive,
                      output=sys.stdout,
                      async=async,
                      read_only=params.readonly)

        if not interactive:
            rc = 0
            try:
                if params.run_once != "":
                    rc = 0 if shell.onecmd(params.run_once) == None else 1
                else:
                    rc = 0
                    for cmd in sys.stdin.readlines():
                        shell.onecmd(cmd.rstrip())
            except IOError:
                rc = 1

            sys.exit(rc)

        if not params.sync_connect:
            signal.signal(signal.SIGUSR2, sigusr_handler)

        intro = "Welcome to zk-shell (%s)" % (__version__)
        first = True
        while True:
            try:
                shell.run(intro if first else None)
            except StateTransition:
                pass
            except KeyboardInterrupt:
                done = raw_input("\nExit? (y|n) ")
                if done == "y":
                    break
            first = False
