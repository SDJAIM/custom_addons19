from . import models
from . import wizard

def post_load_hook():
    """Hook called when module is loaded"""
    from .hooks import post_load_hook as _post_load_hook
    return _post_load_hook()

def post_init_hook(env):
    """Hook called after module installation"""
    from .hooks import post_init_hook as _post_init_hook
    return _post_init_hook(env.cr, env.registry)

def uninstall_hook(env):
    """Hook called when module is uninstalled"""
    from .hooks import uninstall_hook as _uninstall_hook
    return _uninstall_hook(env.cr, env.registry)