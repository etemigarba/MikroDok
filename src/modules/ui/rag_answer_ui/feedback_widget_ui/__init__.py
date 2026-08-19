"""
MikroDok Feedback Widget UI Package
Provides user feedback collection and rating functionality for RAG answers.
Phase: 4
Location: /src/modules/ui/rag_answer_ui/feedback_widget_ui/
"""

# Import feedback widget components
try:
    from .feedback_widget_ui import (
        FeedbackWidgetUI,
        FeedbackType,
        FeedbackRating,
        FeedbackData,
        FeedbackSubmission,
        FeedbackAnalytics,
        FeedbackTrend
    )
except ImportError:
    pass

__all__ = [
    'FeedbackWidgetUI',
    'FeedbackType',
    'FeedbackRating', 
    'FeedbackData',
    'FeedbackSubmission',
    'FeedbackAnalytics',
    'FeedbackTrend'
]
