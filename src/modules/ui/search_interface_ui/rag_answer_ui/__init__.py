"""
RAG Answer UI Module for Search Interface
Description: Comprehensive RAG answer interface component for MikroDok's Interactive Search functionality
Phase: 4
Location: /src/modules/ui/search_interface_ui/rag_answer_ui/
"""

from .rag_answer_ui import (
    RAGAnswerUI,
    RAGAnswerLayout,
    RAGAnswerView,
    RAGAnswerConfig,
    RAGAnswerState
)

# Import from existing RAG answer components
try:
    from src.modules.ui.rag_answer_ui.answer_box_ui.answer_box_ui import (
        AnswerBoxUI,
        RAGAnswer,
        AnswerState,
        SourceReference
    )
except ImportError:
    pass

try:
    from src.modules.ui.rag_answer_ui.source_panel_ui.source_panel_ui import (
        SourcePanelUI,
        SourceDisplayMode,
        SourceSortOption,
        SourceFilterOption,
        SourceDocument
    )
except ImportError:
    pass

try:
    from src.modules.ui.rag_answer_ui.feedback_widget_ui.feedback_widget_ui import (
        FeedbackWidgetUI,
        FeedbackType,
        FeedbackRating,
        FeedbackData
    )
except ImportError:
    pass

# Package metadata
__version__ = "1.0.0"
__author__ = "MikroDok Development Team"
__description__ = "RAG answer interface component for search interface"

# Export main components
__all__ = [
    "RAGAnswerUI",
    "RAGAnswerLayout",
    "RAGAnswerView",
    "RAGAnswerConfig",
    "RAGAnswerState",
    "AnswerBoxUI",
    "RAGAnswer",
    "AnswerState",
    "SourceReference",
    "SourcePanelUI",
    "SourceDisplayMode",
    "SourceSortOption",
    "SourceFilterOption",
    "SourceDocument",
    "FeedbackWidgetUI",
    "FeedbackType",
    "FeedbackRating",
    "FeedbackData"
]
