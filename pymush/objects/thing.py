from .base import GameObject


class Thing(GameObject):
    type_name = "THING"
    cmd_matchers = ("thing", "script")
    can_be_puppet = True
