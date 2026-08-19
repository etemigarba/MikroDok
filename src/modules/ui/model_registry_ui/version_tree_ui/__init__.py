"""
MikroDok Version Tree UI Package
Provides git-style version tree visualization for model versions with branching and merging display.
"""

# Import version tree components
try:
    from .version_tree_ui import VersionTreeUI
except ImportError:
    pass

__all__ = [
    'VersionTreeUI'
]
