"""
MikroDok Progress Overlay UI Package
Provides progress overlays for long-running operations with comprehensive progress tracking and user interaction.
"""

# Import progress overlay components
try:
    from .progress_overlay_ui import (
        ProgressOverlayUI,
        ProgressConfig,
        ProgressType,
        ProgressState,
        OverlayPosition,
        OverlayAnimation,
        ProgressBehavior,
        ProgressContext,
        ProgressResult,
        create_progress_overlay,
        show_progress_overlay
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "Progress overlay UI components for MikroDok application"

# Export main components
__all__ = [
    "ProgressOverlayUI",
    "ProgressConfig",
    "ProgressType",
    "ProgressState",
    "OverlayPosition",
    "OverlayAnimation",
    "ProgressBehavior",
    "ProgressContext",
    "ProgressResult",
    "create_progress_overlay",
    "show_progress_overlay"
]
