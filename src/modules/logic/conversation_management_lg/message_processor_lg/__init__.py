"""
MikroDok Message Processor Package
Provides message processing functionality including validation, formatting, and metadata handling.
"""

# Import message processor components
try:
    from .message_processor_lg import (
        MessageProcessor,
        MessageValidator,
        MetadataExtractor,
        ContentFormatter
    )
except ImportError:
    pass

__all__ = [
    'MessageProcessor',
    'MessageValidator',
    'MetadataExtractor',
    'ContentFormatter'
]
