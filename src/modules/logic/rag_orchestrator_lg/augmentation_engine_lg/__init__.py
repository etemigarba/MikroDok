"""
MikroDok RAG Augmentation Engine Package
Provides prompt augmentation functionality for enhancing queries with retrieved context.
"""

try:
    from .augmentation_engine_lg import (
        AugmentationEngine,
        ContextCompressor,
        TemplateValidator
    )
except ImportError:
    pass

__all__ = [
    'AugmentationEngine',
    'ContextCompressor',
    'TemplateValidator'
]
