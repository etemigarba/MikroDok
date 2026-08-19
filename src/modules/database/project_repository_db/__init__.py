"""
MikroDok Project Repository Database Package
Provides database modules for project management, data access operations, and configuration storage.
"""

# Import project repository database components
try:
    from .project_dao_db.project_dao_db import ProjectDAODB
except ImportError:
    pass

try:
    from .project_settings_db.project_settings_db import ProjectSettingsDB
except ImportError:
    pass

# Import entity models
try:
    from .entities import (
        Project,
        ProjectSettings,
        ProjectMetadata,
        ProjectSettingEntry,
        ProjectStatus,
        ProjectType,
        SettingType,
        SettingCategory
    )
except ImportError:
    pass

__all__ = [
    # Database components
    'ProjectDAODB',
    'ProjectSettingsDB',
    
    # Entity models
    'Project',
    'ProjectSettings',
    'ProjectMetadata',
    'ProjectSettingEntry',
    
    # Enumerations
    'ProjectStatus',
    'ProjectType',
    'SettingType',
    'SettingCategory'
]
