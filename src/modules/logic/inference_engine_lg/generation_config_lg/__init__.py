"""
MikroDok Generation Config Package
Provides generation configuration management functionality.
"""

try:
    from .generation_config_lg import (
        GenerationConfigManager,
        ConfigurationError
    )
except ImportError:
    pass

__all__ = [
    'GenerationConfigManager',
    'ConfigurationError'
]
