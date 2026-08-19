"""
MikroDok Overlap Manager Package
Provides chunk overlap management functionality for context continuity.
"""

# Import overlap manager components
from .overlap_manager_lg import (
    OverlapManager,
    OverlapConfig,
    OverlapCalculator,
    ContextPreserver
)

__all__ = [
    'OverlapManager',
    'OverlapConfig',
    'OverlapCalculator',
    'ContextPreserver'
]
