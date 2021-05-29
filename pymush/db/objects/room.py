from . base import GameObject


class Room(GameObject):
    type_name = 'ROOM'
    can_be_destination = True
