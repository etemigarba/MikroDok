"""
MikroDok Result Card UI Package
Provides individual search result card components for the Interactive Search (RAG) functionality.
"""

# Import result card components
try:
    from .result_card_ui import (
        ResultCardUI,
        ResultCard,
        CardLayout
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Result card UI components for MikroDok search results"

# Export main components
__all__ = [
    "ResultCardUI",
    "ResultCard", 
    "CardLayout"
]
