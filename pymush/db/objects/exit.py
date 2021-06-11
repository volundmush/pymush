from .base import GameObject


class Exit(GameObject):
    type_name = "EXIT"
    can_have_destination = True
