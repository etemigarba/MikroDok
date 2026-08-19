"""
MikroDok Document Viewer UI Package
Provides comprehensive document viewing interface components including preview, chunk visualization, and metadata display.
"""

# Import document preview components
try:
    from .document_preview_ui import (
        DocumentPreviewUI,
        PreviewMode,
        DocumentViewerConfig,
        PreviewState
    )
except ImportError:
    pass

# Import chunk visualizer components
try:
    from .chunk_visualizer_ui import (
        ChunkVisualizerUI,
        ChunkDisplayMode,
        ChunkBoundary
    )
except ImportError:
    pass

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
    # Document Preview
    'DocumentPreviewUI',
    'PreviewMode',
    'DocumentViewerConfig',
    'PreviewState',

    # Chunk Visualizer
    'ChunkVisualizerUI',
    'ChunkDisplayMode',
    'ChunkBoundary',

    # Metadata Panel
    'MetadataPanelUI',
    'MetadataDisplayMode',
    'MetadataField',
    'MetadataSection',
    'MetadataFieldType'
]
