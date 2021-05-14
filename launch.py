#!/usr/bin/env python

from pymush.app import Application


def main():
    config = {
        "interfaces": {
            "external": "192.168.1.51"
        },
        "listeners": {
            "telnet": {
                "interface": "external",
                "port": 7999,
                "protocol": 0
            }
        }
    }
    app = Application(config)
    app.setup()
    app.run()


if __name__ == "__main__":
    main()
