"""
MikroDok Training Configuration Database Package
Provides database modules for training configuration storage, versioning, and preset management.
"""

# Import training configuration database components
try:
    from .config_repository_db.config_repository_db import ConfigRepositoryDB
except ImportError:
    pass

try:
    from .config_versioning_db.config_versioning_db import ConfigVersioningDB
except ImportError:
    pass

try:
    from .preset_manager_db.preset_manager_db import PresetManagerDB
except ImportError:
    pass

__all__ = [
    'ConfigRepositoryDB',
    'ConfigVersioningDB',
    'PresetManagerDB'
]
