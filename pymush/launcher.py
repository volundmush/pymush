#!/usr/bin/env python

import argparse
import os
import sys
import shutil
import subprocess
import shlex
import signal
import importlib

import pymush
from pymush.utils import partial_match

PYMUSH_ROOT = os.path.abspath(os.path.dirname(pymush.__file__))
PYMUSH_APP = os.path.join(PYMUSH_ROOT, 'startup.py')
PYMUSH_PROFILE = os.path.abspath(os.path.join(PYMUSH_ROOT, 'profile_template'))

PROFILE_PATH = None

APPLICATIONS = []


def create_parser():
    parser = argparse.ArgumentParser(description="BOO", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--init", nargs=1, action="store", dest="init", metavar="<folder>")
    parser.add_argument("--app", nargs=1, action="store", dest="app", metavar="<folder>")
    parser.add_argument("operation", nargs="?", action="store", metavar="<operation>", default="_noop")
    return parser


def set_profile_path(args):
    global PROFILE_PATH, PROFILE_PIDFILE
    PROFILE_PATH = os.getcwd()
    if not os.path.exists(os.path.join(PROFILE_PATH, 'appdata')):
        raise ValueError("Current directory is not a valid PyMUSH profile!")


def ensure_running(app):
    pidfile = os.path.join(os.getcwd(), f"{app}.pid")
    if not os.path.exists(pidfile):
        raise ValueError(f"Process {app} is not running!")
    with open(pidfile, "r") as p:
        if not (pid := int(p.read())):
            raise ValueError(f"Process pid for {app} corrupted.")
    try:
        # This doesn't actually do anything except verify that the process exists.
        os.kill(pid, 0)
    except OSError:
        print(f"Process ID for {app} seems stale. Removing stale pidfile.")
        os.remove(pidfile)
        return False
    return True


def ensure_stopped(app):
    pidfile = os.path.join(os.getcwd(), f"{app}.pid")
    if not os.path.exists(pidfile):
        return True
    with open(pidfile, "r") as p:
        if not (pid := int(p.read())):
            raise ValueError(f"Process pid for {app} corrupted.")
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    return False


def operation_start(op, args, unknown):
    for app in APPLICATIONS:
        if not ensure_stopped(app):
            raise ValueError(f"Process {app} is already running!")
    for app in APPLICATIONS:
        env = os.environ.copy()
        env['PYMUSH_PROFILE'] = PROFILE_PATH
        env["PYMUSH_APPNAME"] = app
        cmd = f"{sys.executable} {PYMUSH_APP}"
        subprocess.Popen(shlex.split(cmd), env=env)


def operation_noop(op, args, unknown):
    pass


def operation_stop(op, args, unknown):
    for app in APPLICATIONS:
        if not ensure_running(app):
            raise ValueError(f"Process {app} is not running.")
    for app in APPLICATIONS:
        pidfile = os.path.join(os.getcwd(), f"{app}.pid")
        with open(pidfile, "r") as p:
            if not (pid := int(p.read())):
                raise ValueError(f"Process pid for {app} corrupted.")
        os.kill(pid, signal.SIGTERM)
        os.remove(pidfile)
        print(f"Stopped process {pid} - {app}")


def operation_passthru(op, args, unknown):
    """
    God only knows what people typed here. Let Django figure it out.
    """
    try:
        launcher_module = importlib.import_module('appdata.launcher')
        launcher = launcher_module.RunOperation
    except Exception as e:
        raise Exception(f"Unsupported command {op}")

    try:
        launcher(op, args, unknown)
    except Exception as e:
        print(e)
        raise Exception(f"Could not import settings!")


def option_init(name, un_args):
    prof_path = os.path.join(os.getcwd(), name)
    if not os.path.exists(prof_path):
        shutil.copytree(PYMUSH_PROFILE, prof_path)
        os.rename(os.path.join(prof_path, 'gitignore'), os.path.join(prof_path, '.gitignore'))
        print(f"Profile created at {prof_path}")
    else:
        print(f"Profile at {prof_path} already exists!")


CHOICES = ['start', 'stop', 'noop']

OPERATIONS = {
    '_noop': operation_noop,
    'start': operation_start,
    'stop': operation_stop,
    '_passthru': operation_passthru,
}


def main():
    global APPLICATIONS
    parser = create_parser()
    args, unknown_args = parser.parse_known_args()

    option = args.operation.lower()
    operation = option

    if option not in CHOICES:
        option = '_passthru'

    try:
        if args.init:
            option_init(args.init[0], unknown_args)
            option = '_noop'
            operation = '_noop'

        if option in ['start', 'stop', '_passthru']:
            set_profile_path(args)
            os.chdir(PROFILE_PATH)
            import sys
            sys.path.insert(0, os.getcwd())
            from appdata.config import Launcher
            l_config = Launcher()
            if args.app:
                if not (found := partial_match(args.app[0], l_config.applications)):
                    raise ValueError(f"No registered PyMUSH application: {args.app[0]}")
                APPLICATIONS = [found]
            else:
                APPLICATIONS = l_config.applications

        if not (op_func := OPERATIONS.get(option, None)):
            raise ValueError(f"No operation: {option}")
        op_func(operation, args, unknown_args)

    except Exception as e:
        import sys
        import traceback
        traceback.print_exc(file=sys.stdout)
        print(f"Something done goofed: {e}")
