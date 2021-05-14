#!/usr/bin/env python3.8
import os
import sys
import setproctitle
from pymush.utils import import_from_module
import traceback
import mudstring
from rich import pretty

mudstring.install()
pretty.install()


def main():
    if (new_cwd := os.environ.get("PYMUSH_PROFILE")):
        if not os.path.exists(new_cwd):
            raise ValueError("Improper PyMUSH profile!")
        os.chdir(os.path.abspath(new_cwd))
        sys.path.insert(0, os.getcwd())

    if not (app_name := os.environ.get("PYMUSH_APPNAME")):
        raise ValueError("Improper environment variables. needs PYMUSH_APPNAME")

    # Step 1: get settings from profile.
    try:
        conf = import_from_module(f'appdata.{app_name}.Config')
    except Exception:
        raise Exception("Could not import config!")

    config = conf()
    setproctitle.setproctitle(config.process_name)
    config.setup()

    # Step 2: Locate application Core from settings. Instantiate
    if not (core_class := import_from_module(config.application)):
        raise ValueError(f"Cannot import {app_name} from config applications")

    pidfile = os.path.join('.', f'{app_name}.pid')
    with open(pidfile, 'w') as p:
        p.write(str(os.getpid()))

    app_core = core_class(config)
    try:
        # Step 3: Load application from core.
        app_core.setup()
        # Step 4: Start everything up and run forever.
        if app_core.run_async:
            app_core.start_async()
        else:
            app_core.start()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print(f"UNHANDLED EXCEPTION!")
    finally:
        os.remove(pidfile)

if __name__ == "__main__":
    main()
