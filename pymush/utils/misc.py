from inspect import getmembers, getmodule
import importlib

def callables_from_module(module: str):
    mod = importlib.import_module(module)
    if not mod:
        return {}
    # make sure to only return callables actually defined in this module (not imports)
    members = getmembers(mod, predicate=lambda obj: callable(obj) and getmodule(obj) == mod)
    return dict((key, val) for key, val in members if not key.startswith("_"))