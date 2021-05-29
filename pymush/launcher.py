import pymush
import os
from athanor.launcher import AthanorLauncher


class PyMUSHLauncher(AthanorLauncher):
    name = "PyMUSH"
    root = os.path.abspath(os.path.dirname(pymush.__file__))
    game_template = os.path.abspath(
        os.path.join(os.path.abspath(os.path.dirname(pymush.__file__)), 'game_template'))