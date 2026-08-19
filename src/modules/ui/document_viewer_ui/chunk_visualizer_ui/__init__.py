"""
MikroDok Chunk Visualizer UI Package
Provides document chunk visualization functionality for RAG processing including chunk boundaries, overlap regions, and token counts.
"""

# Import chunk visualizer components
try:
    from .chunk_visualizer_ui import (
        ChunkVisualizerUI,
        ChunkDisplayMode,
        ChunkBoundary,
        ChunkVisualizationConfig,
        ChunkHighlightStyle,
        OverlapRegion
    )
except ImportError:
    pass

__all__ = [
    'ChunkVisualizerUI',
    'ChunkDisplayMode',
    'ChunkBoundary',
    'ChunkVisualizationConfig',
    'ChunkHighlightStyle',
    'OverlapRegion'
]
