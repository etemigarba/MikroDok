"""
MikroDok Metadata Panel UI Package
Provides comprehensive document metadata display and editing interface components.
"""

# Import metadata panel components
try:
    from .metadata_panel_ui import (
        MetadataPanelUI,
        MetadataDisplayMode,
        MetadataField,
        MetadataSection,
        MetadataFieldType
    )
except ImportError:
    pass

__all__ = [
    'MetadataPanelUI',
    'MetadataDisplayMode',
    'MetadataField',
    'MetadataSection',
    'MetadataFieldType'
]
