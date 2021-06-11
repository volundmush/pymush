import importlib
from inspect import getmembers, getmodule


def callables_from_module(module: str):
    mod = importlib.import_module(module)
    if not mod:
        return {}
    # make sure to only return callables actually defined in this module (not imports)
    members = getmembers(
        mod, predicate=lambda obj: callable(obj) and getmodule(obj) == mod
    )
    fixed = {v[0]: v[1] for v in members if not v[0].startswith("_")}
    return fixed
