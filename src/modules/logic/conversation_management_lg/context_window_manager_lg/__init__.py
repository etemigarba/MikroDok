"""
MikroDok Context Window Manager Package
Provides context window management functionality including token counting, boundary management, and context optimization.
"""

# Import context window manager components
try:
    from .context_window_manager_lg import (
        ContextWindowManager,
        TokenCounter,
        BoundaryManager,
        ContextOptimizer
    )
except ImportError:
    pass

__all__ = [
    'ContextWindowManager',
    'TokenCounter',
    'BoundaryManager',
    'ContextOptimizer'
]
