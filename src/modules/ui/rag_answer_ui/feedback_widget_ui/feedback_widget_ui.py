"""
Module: feedback_widget_ui
Description: User feedback collection and rating widget for RAG answer quality improvement with comprehensive
            theming integration. Provides responsive feedback interface with rating systems, comment collection,
            analytics visualization, and quality tracking for RAG (Retrieval Augmented Generation) responses.
Phase: 4
Location: /src/modules/ui/rag_answer_ui/feedback_widget_ui/feedback_widget_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import logging
import json
import uuid

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback that can be collected."""
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"
    INCOMPLETE = "incomplete"
    IRRELEVANT = "irrelevant"
    EXCELLENT = "excellent"
    GOOD = "good"
    POOR = "poor"
    REPORT_ISSUE = "report_issue"
    SUGGEST_IMPROVEMENT = "suggest_improvement"


class FeedbackRating(Enum):
    """Rating scale for feedback."""
    VERY_POOR = 1
    POOR = 2
    FAIR = 3
    GOOD = 4
    EXCELLENT = 5


@dataclass
class FeedbackData:
    """Data structure for feedback information."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    answer_id: str = ""
    user_id: str = ""
    feedback_type: FeedbackType = FeedbackType.HELPFUL
    rating: Optional[FeedbackRating] = None
    comment: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    source_quality: Optional[int] = None
    response_time: Optional[float] = None
    is_anonymous: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackSubmission:
    """Data structure for feedback submission results."""
    success: bool = False
    feedback_id: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_details: Optional[str] = None


@dataclass
class FeedbackAnalytics:
    """Analytics data for feedback trends."""
    total_feedback: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    average_rating: float = 0.0
    feedback_by_type: Dict[FeedbackType, int] = field(default_factory=dict)
    recent_trends: List[Tuple[datetime, int]] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


@dataclass
class FeedbackTrend:
    """Trend data for feedback visualization."""
    date: datetime
    positive_count: int = 0
    negative_count: int = 0
    total_count: int = 0
    average_rating: float = 0.0


class FeedbackWidgetUI(ThemeAwareUserControl):
    """
    User feedback collection widget with comprehensive theming and responsive design.
    
    Features:
    - Responsive feedback interface with adaptive layouts
    - Theme-aware styling with no hardcoded colors or dimensions
    - Multiple feedback types (helpful, rating, comments, reporting)
    - Real-time feedback submission with confirmation
    - Analytics and trend visualization
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Performance optimization for smooth interactions
    - Integration with RAG answer quality improvement system
    - Anonymous and authenticated feedback collection
    - Feedback moderation and quality control
    """
    
    def __init__(
        self,
        answer_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        show_rating: bool = True,
        show_comments: bool = True,
        show_quick_feedback: bool = True,
        show_analytics: bool = False,
        enable_anonymous: bool = True,
        max_comment_length: int = 500,
        on_feedback_submit: Optional[Callable[[FeedbackData], None]] = None,
        on_feedback_update: Optional[Callable[[FeedbackAnalytics], None]] = None,
        **kwargs
    ):
        """
        Initialize the feedback widget UI component.
        
        Args:
            answer_id: ID of the answer being rated
            user_id: ID of the user providing feedback
            session_id: Current session ID
            show_rating: Whether to show star rating system
            show_comments: Whether to show comment input
            show_quick_feedback: Whether to show quick feedback buttons
            show_analytics: Whether to show feedback analytics
            enable_anonymous: Whether to allow anonymous feedback
            max_comment_length: Maximum length for comments
            on_feedback_submit: Callback for feedback submission
            on_feedback_update: Callback for analytics updates
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Configuration
        self._answer_id = answer_id or ""
        self._user_id = user_id or ""
        self._session_id = session_id or str(uuid.uuid4())
        self._show_rating = show_rating
        self._show_comments = show_comments
        self._show_quick_feedback = show_quick_feedback
        self._show_analytics = show_analytics
        self._enable_anonymous = enable_anonymous
        self._max_comment_length = max_comment_length
        
        # Callbacks
        self._on_feedback_submit = on_feedback_submit
        self._on_feedback_update = on_feedback_update
        
        # State
        self._current_feedback: Optional[FeedbackData] = None
        self._selected_rating: Optional[FeedbackRating] = None
        self._selected_type: Optional[FeedbackType] = None
        self._comment_text: str = ""
        self._is_submitting: bool = False
        self._submission_result: Optional[FeedbackSubmission] = None
        self._analytics: Optional[FeedbackAnalytics] = None
        
        # UI References
        self._rating_stars: List[ft.IconButton] = []
        self._comment_field: Optional[ft.TextField] = None
        self._submit_button: Optional[ft.ElevatedButton] = None
        self._feedback_buttons: Dict[FeedbackType, ft.IconButton] = {}
        self._analytics_container: Optional[ft.Container] = None
        
        logger.info(f"FeedbackWidgetUI initialized for answer: {self._answer_id}")

    def build(self) -> ft.Control:
        """Build the feedback widget interface."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()
            
            # Main widget sections
            sections = []
            
            # Quick feedback buttons
            if self._show_quick_feedback:
                sections.append(self._build_quick_feedback_section())
            
            # Rating system
            if self._show_rating:
                sections.append(self._build_rating_section())
            
            # Comment input
            if self._show_comments:
                sections.append(self._build_comment_section())
            
            # Submit section
            sections.append(self._build_submit_section())
            
            # Analytics section
            if self._show_analytics and self._analytics:
                sections.append(self._build_analytics_section())
            
            # Submission result
            if self._submission_result:
                sections.append(self._build_result_section())
            
            return self.create_responsive_container(
                content=ft.Column(
                    controls=sections,
                    spacing=spacing.md,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=spacing.md,
                bgcolor=palette.surface,
                border=ft.border.all(1, palette.outline),
                border_radius=self.get_breakpoint_value(8, 10, 12, 14)
            )
            
        except Exception as e:
            logger.error(f"Error building feedback widget: {e}")
            return self._build_error_state(str(e))

    def _build_quick_feedback_section(self) -> ft.Control:
        """Build quick feedback buttons section."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()
            
            # Quick feedback buttons
            quick_buttons = [
                (FeedbackType.HELPFUL, icons.THUMB_UP, "Helpful", palette.success),
                (FeedbackType.NOT_HELPFUL, icons.THUMB_DOWN, "Not Helpful", palette.error),
                (FeedbackType.EXCELLENT, icons.STAR, "Excellent", palette.primary),
                (FeedbackType.REPORT_ISSUE, ft.Icons.FLAG, "Report Issue", palette.warning)
            ]
            
            button_controls = []
            for feedback_type, icon, tooltip, color in quick_buttons:
                is_selected = self._selected_type == feedback_type
                
                button = ft.IconButton(
                    icon=icon,
                    icon_size=self.get_breakpoint_value(20, 22, 24, 26),
                    icon_color=color if is_selected else palette.on_surface_variant,
                    bgcolor=palette.surface_variant if is_selected else None,
                    tooltip=tooltip,
                    on_click=lambda e, ft=feedback_type: self._handle_quick_feedback(ft)
                )
                
                self._feedback_buttons[feedback_type] = button
                button_controls.append(button)
            
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Quick Feedback",
                            style=typography.label_large,
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Row(
                            controls=button_controls,
                            spacing=spacing.sm,
                            alignment=ft.MainAxisAlignment.START
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )
            
        except Exception as e:
            logger.error(f"Error building quick feedback section: {e}")
            return ft.Container()

    def _build_rating_section(self) -> ft.Control:
        """Build star rating section."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            # Create star rating buttons
            star_controls = []
            for i in range(1, 6):  # 1-5 star rating
                rating = FeedbackRating(i)
                is_selected = self._selected_rating and self._selected_rating.value >= i

                star_button = ft.IconButton(
                    icon=icons.STAR if is_selected else icons.STAR_OUTLINE,
                    icon_size=self.get_breakpoint_value(24, 26, 28, 30),
                    icon_color=palette.warning if is_selected else palette.on_surface_variant,
                    tooltip=f"{i} star{'s' if i > 1 else ''}",
                    on_click=lambda e, r=rating: self._handle_rating_click(r)
                )

                star_controls.append(star_button)
                self._rating_stars.append(star_button)

            # Rating description
            rating_text = ""
            if self._selected_rating:
                rating_descriptions = {
                    FeedbackRating.VERY_POOR: "Very Poor",
                    FeedbackRating.POOR: "Poor",
                    FeedbackRating.FAIR: "Fair",
                    FeedbackRating.GOOD: "Good",
                    FeedbackRating.EXCELLENT: "Excellent"
                }
                rating_text = rating_descriptions.get(self._selected_rating, "")

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Rate this answer",
                            style=typography.label_large,
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Row(
                            controls=star_controls,
                            spacing=spacing.xs,
                            alignment=ft.MainAxisAlignment.START
                        ),
                        ft.Text(
                            rating_text,
                            style=typography.body_medium,
                            color=palette.on_surface_variant,
                            visible=bool(rating_text)
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building rating section: {e}")
            return ft.Container()

    def _build_comment_section(self) -> ft.Control:
        """Build comment input section."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Comment text field
            self._comment_field = ft.TextField(
                label="Additional comments (optional)",
                hint_text="Share your thoughts to help us improve...",
                multiline=True,
                min_lines=3,
                max_lines=6,
                max_length=self._max_comment_length,
                value=self._comment_text,
                text_style=typography.body_medium,
                label_style=typography.label_medium,
                hint_style=typography.body_small,
                color=palette.on_surface,
                bgcolor=palette.surface_variant,
                border_color=palette.outline_variant,
                focused_border_color=palette.primary,
                cursor_color=palette.primary,
                on_change=self._handle_comment_change
            )

            # Character counter
            char_count = len(self._comment_text)
            char_counter = ft.Text(
                f"{char_count}/{self._max_comment_length}",
                style=typography.label_small,
                color=palette.error if char_count > self._max_comment_length else palette.on_surface_variant,
                text_align=ft.TextAlign.RIGHT
            )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        self._comment_field,
                        ft.Row(
                            controls=[char_counter],
                            alignment=ft.MainAxisAlignment.END
                        )
                    ],
                    spacing=spacing.xs,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building comment section: {e}")
            return ft.Container()

    def _build_submit_section(self) -> ft.Control:
        """Build submit button section."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            # Submit button
            self._submit_button = ft.ElevatedButton(
                text="Submit Feedback",
                icon=icons.SEND if not self._is_submitting else icons.LOADING,
                style=ft.ButtonStyle(
                    color=palette.on_primary,
                    bgcolor=palette.primary,
                    text_style=typography.label_large
                ),
                disabled=self._is_submitting or not self._can_submit(),
                on_click=self._handle_submit_click
            )

            # Anonymous checkbox
            anonymous_checkbox = ft.Checkbox(
                label="Submit anonymously",
                value=self._enable_anonymous,
                label_style=typography.body_medium,
                check_color=palette.primary,
                active_color=palette.primary,
                visible=self._enable_anonymous,
                on_change=self._handle_anonymous_change
            )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                self._submit_button,
                                ft.Container(expand=True),  # Spacer
                                anonymous_checkbox
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building submit section: {e}")
            return ft.Container()

    def _build_analytics_section(self) -> ft.Control:
        """Build feedback analytics section."""
        try:
            if not self._analytics:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            # Analytics metrics
            metrics = [
                ("Total Feedback", str(self._analytics.total_feedback), ft.Icons.FEEDBACK),
                ("Positive", str(self._analytics.positive_feedback), icons.THUMB_UP),
                ("Negative", str(self._analytics.negative_feedback), icons.THUMB_DOWN),
                ("Avg Rating", f"{self._analytics.average_rating:.1f}/5", icons.STAR)
            ]

            metric_cards = []
            for label, value, icon in metrics:
                card = ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                icon,
                                size=self.get_breakpoint_value(20, 22, 24, 26),
                                color=palette.primary
                            ),
                            ft.Text(
                                value,
                                style=typography.headline_small,
                                color=palette.on_surface,
                                weight=ft.FontWeight.W_600
                            ),
                            ft.Text(
                                label,
                                style=typography.label_small,
                                color=palette.on_surface_variant
                            )
                        ],
                        spacing=spacing.xs,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        tight=True
                    ),
                    padding=spacing.sm,
                    bgcolor=palette.surface_variant,
                    border_radius=8,
                    expand=True
                )
                metric_cards.append(card)

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Feedback Analytics",
                            style=typography.label_large,
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Row(
                            controls=metric_cards,
                            spacing=spacing.sm
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building analytics section: {e}")
            return ft.Container()

    def _build_result_section(self) -> ft.Control:
        """Build submission result section."""
        try:
            if not self._submission_result:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            # Result styling based on success/failure
            if self._submission_result.success:
                icon = icons.CHECK_CIRCLE
                color = palette.success
                bg_color = self.get_success_with_opacity(0.1)
            else:
                icon = icons.ERROR
                color = palette.error
                bg_color = self.get_error_with_opacity(0.1)

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icon,
                            size=self.get_breakpoint_value(20, 22, 24, 26),
                            color=color
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    self._submission_result.message,
                                    style=typography.body_medium,
                                    color=palette.on_surface,
                                    weight=ft.FontWeight.W_500
                                ),
                                ft.Text(
                                    f"Submitted at {self._submission_result.timestamp.strftime('%H:%M:%S')}",
                                    style=typography.label_small,
                                    color=palette.on_surface_variant
                                ) if self._submission_result.success else ft.Container()
                            ],
                            spacing=spacing.xs,
                            tight=True,
                            expand=True
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                padding=spacing.sm,
                bgcolor=bg_color,
                border=ft.border.all(1, color),
                border_radius=8
            )

        except Exception as e:
            logger.error(f"Error building result section: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str) -> ft.Control:
        """Build error state display."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            icons.ERROR_OUTLINE,
                            size=self.get_breakpoint_value(32, 36, 40, 44),
                            color=palette.error
                        ),
                        ft.Text(
                            "Feedback Widget Error",
                            style=typography.headline_small,
                            color=palette.on_surface,
                            weight=ft.FontWeight.W_600,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            error_message,
                            style=typography.body_medium,
                            color=palette.on_surface_variant,
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True
                ),
                padding=spacing.lg,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    # Event Handlers
    def _handle_quick_feedback(self, feedback_type: FeedbackType) -> None:
        """Handle quick feedback button click."""
        try:
            self._selected_type = feedback_type

            # Auto-set rating based on feedback type
            if feedback_type == FeedbackType.HELPFUL:
                self._selected_rating = FeedbackRating.GOOD
            elif feedback_type == FeedbackType.NOT_HELPFUL:
                self._selected_rating = FeedbackRating.POOR
            elif feedback_type == FeedbackType.EXCELLENT:
                self._selected_rating = FeedbackRating.EXCELLENT

            # Update UI
            self._update_ui_state()

            logger.info(f"Quick feedback selected: {feedback_type.value}")

        except Exception as e:
            logger.error(f"Error handling quick feedback: {e}")

    def _handle_rating_click(self, rating: FeedbackRating) -> None:
        """Handle star rating click."""
        try:
            self._selected_rating = rating

            # Auto-set feedback type based on rating
            if rating.value >= 4:
                self._selected_type = FeedbackType.HELPFUL
            elif rating.value <= 2:
                self._selected_type = FeedbackType.NOT_HELPFUL
            else:
                self._selected_type = FeedbackType.HELPFUL  # Neutral positive

            # Update UI
            self._update_ui_state()

            logger.info(f"Rating selected: {rating.value} stars")

        except Exception as e:
            logger.error(f"Error handling rating click: {e}")

    def _handle_comment_change(self, e) -> None:
        """Handle comment text change."""
        try:
            self._comment_text = e.control.value or ""

            # Update character counter and submit button state
            self._update_ui_state()

        except Exception as e:
            logger.error(f"Error handling comment change: {e}")

    def _handle_anonymous_change(self, e) -> None:
        """Handle anonymous checkbox change."""
        try:
            self._enable_anonymous = e.control.value
            logger.info(f"Anonymous feedback: {self._enable_anonymous}")

        except Exception as e:
            logger.error(f"Error handling anonymous change: {e}")

    async def _handle_submit_click(self, e) -> None:
        """Handle submit button click."""
        try:
            if not self._can_submit():
                return

            self._is_submitting = True
            self._update_ui_state()

            # Create feedback data
            feedback_data = FeedbackData(
                answer_id=self._answer_id,
                user_id="" if self._enable_anonymous else self._user_id,
                session_id=self._session_id,
                feedback_type=self._selected_type or FeedbackType.HELPFUL,
                rating=self._selected_rating,
                comment=self._comment_text.strip(),
                is_anonymous=self._enable_anonymous,
                metadata={
                    "widget_version": "1.0",
                    "submission_method": "ui_widget"
                }
            )

            # Submit feedback
            result = await self._submit_feedback(feedback_data)

            # Update UI with result
            self._submission_result = result
            self._is_submitting = False

            if result.success:
                # Reset form on successful submission
                self._reset_form()

            self._update_ui_state()

            logger.info(f"Feedback submission result: {result.success}")

        except Exception as e:
            logger.error(f"Error handling submit click: {e}")
            self._is_submitting = False
            self._submission_result = FeedbackSubmission(
                success=False,
                message="Failed to submit feedback",
                error_details=str(e)
            )
            self._update_ui_state()

    async def _submit_feedback(self, feedback_data: FeedbackData) -> FeedbackSubmission:
        """Submit feedback data."""
        try:
            # Simulate API call delay
            await asyncio.sleep(0.5)

            # Call submission callback if provided
            if self._on_feedback_submit:
                self._on_feedback_submit(feedback_data)

            # Simulate successful submission
            return FeedbackSubmission(
                success=True,
                feedback_id=feedback_data.id,
                message="Thank you for your feedback!"
            )

        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            return FeedbackSubmission(
                success=False,
                message="Failed to submit feedback",
                error_details=str(e)
            )

    # Utility Methods
    def _can_submit(self) -> bool:
        """Check if feedback can be submitted."""
        return (
            not self._is_submitting and
            (self._selected_type is not None or
             self._selected_rating is not None or
             self._comment_text.strip())
        )

    def _reset_form(self) -> None:
        """Reset form to initial state."""
        try:
            self._selected_rating = None
            self._selected_type = None
            self._comment_text = ""
            self._current_feedback = None

            # Clear UI references
            if self._comment_field:
                self._comment_field.value = ""

            logger.info("Feedback form reset")

        except Exception as e:
            logger.error(f"Error resetting form: {e}")

    def _update_ui_state(self) -> None:
        """Update UI state and refresh display."""
        try:
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error updating UI state: {e}")

    # Public Methods
    def set_answer_id(self, answer_id: str) -> None:
        """Set the answer ID for feedback tracking."""
        try:
            self._answer_id = answer_id
            logger.info(f"Answer ID set to: {answer_id}")

        except Exception as e:
            logger.error(f"Error setting answer ID: {e}")

    def set_user_id(self, user_id: str) -> None:
        """Set the user ID for feedback attribution."""
        try:
            self._user_id = user_id
            logger.info(f"User ID set for feedback widget")

        except Exception as e:
            logger.error(f"Error setting user ID: {e}")

    def set_analytics(self, analytics: FeedbackAnalytics) -> None:
        """Set analytics data for display."""
        try:
            self._analytics = analytics

            if self._show_analytics:
                self._update_ui_state()

            logger.info("Analytics data updated")

        except Exception as e:
            logger.error(f"Error setting analytics: {e}")

    def get_current_feedback(self) -> Optional[FeedbackData]:
        """Get current feedback data."""
        try:
            if not self._selected_type and not self._selected_rating and not self._comment_text:
                return None

            return FeedbackData(
                answer_id=self._answer_id,
                user_id="" if self._enable_anonymous else self._user_id,
                session_id=self._session_id,
                feedback_type=self._selected_type or FeedbackType.HELPFUL,
                rating=self._selected_rating,
                comment=self._comment_text.strip(),
                is_anonymous=self._enable_anonymous
            )

        except Exception as e:
            logger.error(f"Error getting current feedback: {e}")
            return None

    def clear_feedback(self) -> None:
        """Clear current feedback and reset form."""
        try:
            self._reset_form()
            self._submission_result = None
            self._update_ui_state()

            logger.info("Feedback cleared")

        except Exception as e:
            logger.error(f"Error clearing feedback: {e}")

    def set_feedback_data(self, feedback_data: FeedbackData) -> None:
        """Set feedback data to display existing feedback."""
        try:
            self._current_feedback = feedback_data
            self._selected_type = feedback_data.feedback_type
            self._selected_rating = feedback_data.rating
            self._comment_text = feedback_data.comment

            # Update UI fields
            if self._comment_field:
                self._comment_field.value = self._comment_text

            self._update_ui_state()

            logger.info(f"Feedback data loaded: {feedback_data.id}")

        except Exception as e:
            logger.error(f"Error setting feedback data: {e}")

    def enable_analytics_display(self, enable: bool = True) -> None:
        """Enable or disable analytics display."""
        try:
            self._show_analytics = enable
            self._update_ui_state()

            logger.info(f"Analytics display: {'enabled' if enable else 'disabled'}")

        except Exception as e:
            logger.error(f"Error toggling analytics display: {e}")

    def get_submission_result(self) -> Optional[FeedbackSubmission]:
        """Get the last submission result."""
        return self._submission_result

    def is_submitting(self) -> bool:
        """Check if feedback is currently being submitted."""
        return self._is_submitting

    def has_feedback(self) -> bool:
        """Check if user has provided any feedback."""
        return (
            self._selected_type is not None or
            self._selected_rating is not None or
            bool(self._comment_text.strip())
        )

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of current feedback state."""
        try:
            return {
                "has_feedback": self.has_feedback(),
                "feedback_type": self._selected_type.value if self._selected_type else None,
                "rating": self._selected_rating.value if self._selected_rating else None,
                "comment_length": len(self._comment_text),
                "is_anonymous": self._enable_anonymous,
                "can_submit": self._can_submit(),
                "is_submitting": self._is_submitting,
                "submission_success": self._submission_result.success if self._submission_result else None
            }

        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")
            return {}

    def validate_feedback(self) -> Tuple[bool, List[str]]:
        """Validate current feedback data."""
        try:
            errors = []

            # Check if any feedback is provided
            if not self.has_feedback():
                errors.append("Please provide at least one form of feedback")

            # Validate comment length
            if len(self._comment_text) > self._max_comment_length:
                errors.append(f"Comment exceeds maximum length of {self._max_comment_length} characters")

            # Check for required fields based on feedback type
            if self._selected_type == FeedbackType.REPORT_ISSUE and not self._comment_text.strip():
                errors.append("Please provide details when reporting an issue")

            return len(errors) == 0, errors

        except Exception as e:
            logger.error(f"Error validating feedback: {e}")
            return False, ["Validation error occurred"]
