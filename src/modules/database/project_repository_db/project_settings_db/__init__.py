"""
MikroDok Project Settings Database Package
Provides project-specific configuration and user preference management with JSON storage support.
"""

# Import project settings database components
try:
    from .project_settings_db import ProjectSettingsDB
except ImportError:
    pass

__all__ = [
    'ProjectSettingsDB'
]
