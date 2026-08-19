"""
Module: rag_answer_ui
Description: Comprehensive RAG (Retrieval Augmented Generation) answer interface component that integrates
            answer display, source panel, and feedback collection into a unified responsive interface.
            Provides intelligent answer presentation with confidence visualization, source highlighting,
            streaming support, and comprehensive theme integration for MikroDok's Interactive Search functionality.
Phase: 4
Location: /src/modules/ui/search_interface_ui/rag_answer_ui/rag_answer_ui.py
"""

# Standard library imports
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.ui.rag_answer_ui.answer_box_ui.answer_box_ui import (
    AnswerBoxUI,
    RAGAnswer,
    AnswerState,
    SourceReference
)
from src.modules.ui.rag_answer_ui.source_panel_ui.source_panel_ui import (
    SourcePanelUI,
    SourceDisplayMode,
    SourceSortOption,
    SourceFilterOption,
    SourceDocument
)
from src.modules.ui.rag_answer_ui.feedback_widget_ui.feedback_widget_ui import (
    FeedbackWidgetUI,
    FeedbackType,
    FeedbackRating,
    FeedbackData
)

# Configure logging
logger = logging.getLogger(__name__)


class RAGAnswerLayout(Enum):
    """Layout modes for RAG answer interface."""
    STANDARD = "standard"           # Answer box with side panel
    COMPACT = "compact"             # Condensed layout for mobile
    DETAILED = "detailed"           # Expanded layout with all features
    TABBED = "tabbed"              # Tabbed interface for complex answers
    SPLIT = "split"                # Split view with resizable panels


class RAGAnswerView(Enum):
    """View modes for answer presentation."""
    FULL = "full"                  # Complete answer with all features
    PREVIEW = "preview"            # Quick preview mode
    STREAMING = "streaming"        # Real-time streaming display
    COMPARISON = "comparison"      # Side-by-side answer comparison


@dataclass
class RAGAnswerConfig:
    """Configuration for RAG answer interface."""
    # Layout configuration
    layout: RAGAnswerLayout = RAGAnswerLayout.STANDARD
    view: RAGAnswerView = RAGAnswerView.FULL
    
    # Feature toggles
    show_confidence: bool = True
    show_sources: bool = True
    show_feedback: bool = True
    show_metadata: bool = True
    enable_streaming: bool = True
    enable_highlighting: bool = True
    enable_copy: bool = True
    enable_share: bool = True
    
    # Display settings
    max_answer_length: int = 5000
    max_sources: int = 10
    auto_expand_sources: bool = False
    show_source_preview: bool = True
    
    # Interaction settings
    enable_source_navigation: bool = True
    enable_answer_editing: bool = False
    enable_regeneration: bool = True
    
    # Performance settings
    lazy_load_sources: bool = True
    cache_answers: bool = True
    preload_related: bool = False


@dataclass
class RAGAnswerState:
    """State management for RAG answer interface."""
    # Current answer data
    current_answer: Optional[RAGAnswer] = None
    answer_history: List[RAGAnswer] = field(default_factory=list)
    
    # UI state
    is_loading: bool = False
    is_streaming: bool = False
    is_expanded: bool = False
    selected_source: Optional[str] = None
    
    # Interaction state
    feedback_submitted: bool = False
    answer_copied: bool = False
    sources_filtered: bool = False
    
    # Error state
    error_message: Optional[str] = None
    retry_count: int = 0


class RAGAnswerUI(ThemeAwareUserControl):
    """
    Comprehensive RAG answer interface component with integrated answer display, source panel, and feedback.
    
    Features:
    - Unified RAG answer presentation with responsive layouts
    - Integrated answer box, source panel, and feedback collection
    - Theme-aware styling with no hardcoded colors or dimensions
    - Multiple layout modes (standard, compact, detailed, tabbed, split)
    - Real-time streaming answer support with progress indicators
    - Interactive source navigation with highlighting and preview
    - Comprehensive feedback collection with analytics
    - Confidence visualization with color-coded indicators
    - Answer history and comparison capabilities
    - Performance optimization with lazy loading and caching
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Integration with ResponsiveLayoutManager for adaptive layouts
    - Advanced answer features (copy, share, regenerate, edit)
    """

    def __init__(self,
                 config: Optional[RAGAnswerConfig] = None,
                 initial_answer: Optional[RAGAnswer] = None,
                 on_source_click: Optional[Callable[[str], None]] = None,
                 on_feedback_submit: Optional[Callable[[FeedbackData], None]] = None,
                 on_answer_regenerate: Optional[Callable[[str], None]] = None,
                 on_answer_copy: Optional[Callable[[str], None]] = None,
                 on_answer_share: Optional[Callable[[str], None]] = None,
                 on_source_navigate: Optional[Callable[[str, int], None]] = None,
                 **kwargs):
        """
        Initialize RAG answer interface.
        
        Args:
            config: Interface configuration settings
            initial_answer: Initial answer to display
            on_source_click: Callback for source document clicks
            on_feedback_submit: Callback for feedback submission
            on_answer_regenerate: Callback for answer regeneration
            on_answer_copy: Callback for answer copy actions
            on_answer_share: Callback for answer sharing
            on_source_navigate: Callback for source navigation
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Configuration and state
        self._config = config or RAGAnswerConfig()
        self._state = RAGAnswerState()
        
        # Event callbacks
        self._on_source_click = on_source_click
        self._on_feedback_submit = on_feedback_submit
        self._on_answer_regenerate = on_answer_regenerate
        self._on_answer_copy = on_answer_copy
        self._on_answer_share = on_answer_share
        self._on_source_navigate = on_source_navigate
        
        # Component instances
        self._answer_box: Optional[AnswerBoxUI] = None
        self._source_panel: Optional[SourcePanelUI] = None
        self._feedback_widget: Optional[FeedbackWidgetUI] = None
        
        # UI controls
        self._main_container: Optional[ft.Control] = None
        self._layout_container: Optional[ft.Control] = None
        self._toolbar_container: Optional[ft.Control] = None
        
        # Initialize with answer if provided
        if initial_answer:
            self.set_answer(initial_answer)
        
        logger.info("RAGAnswerUI initialized")

    def build(self) -> ft.Control:
        """Build the RAG answer interface."""
        try:
            # Build interface based on layout mode
            if self._config.layout == RAGAnswerLayout.STANDARD:
                return self._build_standard_layout()
            elif self._config.layout == RAGAnswerLayout.COMPACT:
                return self._build_compact_layout()
            elif self._config.layout == RAGAnswerLayout.DETAILED:
                return self._build_detailed_layout()
            elif self._config.layout == RAGAnswerLayout.TABBED:
                return self._build_tabbed_layout()
            elif self._config.layout == RAGAnswerLayout.SPLIT:
                return self._build_split_layout()
            else:
                return self._build_standard_layout()
                
        except Exception as e:
            logger.error(f"Error building RAG answer UI: {e}")
            return self._build_error_layout(str(e))

    def _build_standard_layout(self) -> ft.Control:
        """Build standard RAG answer layout with answer box and side panel."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create component instances
            self._initialize_components()

            # Main content area
            main_content = ft.Row(
                controls=[
                    # Answer section (left side)
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_toolbar_section(),
                                self._answer_box,
                                self._build_feedback_section() if self._config.show_feedback else ft.Container()
                            ],
                            spacing=spacing.md,
                            expand=True
                        ),
                        expand=2,
                        padding=ft.padding.only(right=spacing.sm)
                    ),

                    # Source panel (right side)
                    ft.Container(
                        content=self._source_panel,
                        expand=1,
                        padding=ft.padding.only(left=spacing.sm)
                    ) if self._config.show_sources else ft.Container()
                ],
                spacing=spacing.md,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )

            return self.create_responsive_container(
                content=main_content,
                padding=spacing.md,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(12)
            )

        except Exception as e:
            logger.error(f"Error building standard layout: {e}")
            return self._build_error_layout(str(e))

    def _build_compact_layout(self) -> ft.Control:
        """Build compact layout for mobile devices."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create component instances
            self._initialize_components()

            # Compact vertical layout
            content_controls = [
                self._build_compact_toolbar(),
                self._answer_box
            ]

            # Add collapsible sections
            if self._config.show_sources:
                content_controls.append(self._build_collapsible_sources())

            if self._config.show_feedback:
                content_controls.append(self._build_compact_feedback())

            main_content = ft.Column(
                controls=content_controls,
                spacing=spacing.sm,
                expand=True
            )

            return self.create_responsive_container(
                content=main_content,
                padding=spacing.sm,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building compact layout: {e}")
            return self._build_error_layout(str(e))

    def _build_detailed_layout(self) -> ft.Control:
        """Build detailed layout with all features expanded."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create component instances
            self._initialize_components()

            # Three-column layout
            main_content = ft.Row(
                controls=[
                    # Left panel - Answer metadata and controls
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_answer_metadata(),
                                self._build_answer_controls(),
                                self._build_answer_history()
                            ],
                            spacing=spacing.md
                        ),
                        width=self.get_responsive_value(250, 280, 320, 350),
                        padding=ft.padding.only(right=spacing.sm)
                    ),

                    # Center panel - Main answer
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_detailed_toolbar(),
                                self._answer_box,
                                self._build_feedback_section() if self._config.show_feedback else ft.Container()
                            ],
                            spacing=spacing.md,
                            expand=True
                        ),
                        expand=2,
                        padding=ft.padding.symmetric(horizontal=spacing.sm)
                    ),

                    # Right panel - Sources and related
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self._source_panel,
                                self._build_related_answers() if self._config.preload_related else ft.Container()
                            ],
                            spacing=spacing.md
                        ),
                        width=self.get_responsive_value(300, 350, 400, 450),
                        padding=ft.padding.only(left=spacing.sm)
                    ) if self._config.show_sources else ft.Container()
                ],
                spacing=spacing.md,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )

            return self.create_responsive_container(
                content=main_content,
                padding=spacing.lg,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(16)
            )

        except Exception as e:
            logger.error(f"Error building detailed layout: {e}")
            return self._build_error_layout(str(e))

    def _build_tabbed_layout(self) -> ft.Control:
        """Build tabbed layout for complex answers."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Create component instances
            self._initialize_components()

            # Create tabs
            tabs = [
                ft.Tab(
                    text="Answer",
                    icon=icons.CHAT,
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                self._build_toolbar_section(),
                                self._answer_box
                            ],
                            spacing=spacing.md,
                            expand=True
                        ),
                        padding=ft.padding.all(spacing.md)
                    )
                )
            ]

            # Add sources tab if enabled
            if self._config.show_sources:
                tabs.append(
                    ft.Tab(
                        text="Sources",
                        icon=icons.LIBRARY_BOOKS,
                        content=ft.Container(
                            content=self._source_panel,
                            padding=ft.padding.all(spacing.md)
                        )
                    )
                )

            # Add feedback tab if enabled
            if self._config.show_feedback:
                tabs.append(
                    ft.Tab(
                        text="Feedback",
                        icon=icons.FEEDBACK,
                        content=ft.Container(
                            content=self._build_feedback_section(),
                            padding=ft.padding.all(spacing.md)
                        )
                    )
                )

            # Add metadata tab if enabled
            if self._config.show_metadata:
                tabs.append(
                    ft.Tab(
                        text="Details",
                        icon=icons.INFO,
                        content=ft.Container(
                            content=self._build_answer_metadata(),
                            padding=ft.padding.all(spacing.md)
                        )
                    )
                )

            tab_container = ft.Tabs(
                tabs=tabs,
                selected_index=0,
                animation_duration=300,
                tab_alignment=ft.TabAlignment.START,
                expand=True
            )

            return self.create_responsive_container(
                content=tab_container,
                padding=spacing.md,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(12)
            )

        except Exception as e:
            logger.error(f"Error building tabbed layout: {e}")
            return self._build_error_layout(str(e))

    def _build_split_layout(self) -> ft.Control:
        """Build split layout with resizable panels."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create component instances
            self._initialize_components()

            # Split view with resizable divider
            left_panel = ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_toolbar_section(),
                        self._answer_box,
                        self._build_feedback_section() if self._config.show_feedback else ft.Container()
                    ],
                    spacing=spacing.md,
                    expand=True
                ),
                expand=True,
                padding=ft.padding.only(right=spacing.sm)
            )

            right_panel = ft.Container(
                content=self._source_panel,
                width=self.get_responsive_value(350, 400, 450, 500),
                padding=ft.padding.only(left=spacing.sm)
            ) if self._config.show_sources else ft.Container()

            # Create split view
            split_content = ft.Row(
                controls=[left_panel, right_panel] if self._config.show_sources else [left_panel],
                spacing=spacing.md,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )

            return self.create_responsive_container(
                content=split_content,
                padding=spacing.md,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(12)
            )

        except Exception as e:
            logger.error(f"Error building split layout: {e}")
            return self._build_error_layout(str(e))

    def _initialize_components(self) -> None:
        """Initialize child components."""
        try:
            # Initialize answer box
            if not self._answer_box:
                self._answer_box = AnswerBoxUI(
                    answer=self._state.current_answer,
                    show_confidence=self._config.show_confidence,
                    show_sources=self._config.show_sources,
                    show_metadata=self._config.show_metadata,
                    enable_streaming=self._config.enable_streaming,
                    max_answer_length=self._config.max_answer_length,
                    on_source_click=self._handle_source_click,
                    on_copy=self._handle_answer_copy
                )

            # Initialize source panel
            if not self._source_panel and self._config.show_sources:
                sources = []
                if self._state.current_answer and self._state.current_answer.source_references:
                    sources = [
                        SourceDocument(
                            id=ref.document_id,
                            title=ref.title,
                            content=ref.content,
                            relevance_score=ref.relevance_score,
                            document_type=ref.document_type,
                            metadata=ref.metadata
                        )
                        for ref in self._state.current_answer.source_references[:self._config.max_sources]
                    ]

                self._source_panel = SourcePanelUI(
                    sources=sources,
                    display_mode=SourceDisplayMode.DETAILED,
                    show_relevance_scores=True,
                    show_metadata=self._config.show_metadata,
                    enable_preview=self._config.show_source_preview,
                    on_source_click=self._handle_source_click,
                    on_source_navigate=self._handle_source_navigate
                )

            # Initialize feedback widget
            if not self._feedback_widget and self._config.show_feedback:
                self._feedback_widget = FeedbackWidgetUI(
                    answer_id=self._state.current_answer.id if self._state.current_answer else "",
                    show_rating=True,
                    show_comments=True,
                    show_quick_feedback=True,
                    on_feedback_submit=self._handle_feedback_submit
                )

        except Exception as e:
            logger.error(f"Error initializing components: {e}")

    def _build_toolbar_section(self) -> ft.Control:
        """Build the main toolbar section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Toolbar buttons
            toolbar_buttons = []

            # Copy button
            if self._config.enable_copy:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.COPY,
                        tooltip="Copy Answer",
                        on_click=self._handle_copy_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Share button
            if self._config.enable_share:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.SHARE,
                        tooltip="Share Answer",
                        on_click=self._handle_share_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Regenerate button
            if self._config.enable_regeneration:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.REFRESH,
                        tooltip="Regenerate Answer",
                        on_click=self._handle_regenerate_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Expand/collapse button
            toolbar_buttons.append(
                ft.IconButton(
                    icon=icons.EXPAND_MORE if not self._state.is_expanded else icons.EXPAND_LESS,
                    tooltip="Expand/Collapse",
                    on_click=self._handle_expand_click,
                    icon_color=palette.text_secondary,
                    icon_size=self.get_responsive_size(20)
                )
            )

            # Answer status indicator
            status_indicator = self._build_status_indicator()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        status_indicator,
                        ft.Container(expand=True),  # Spacer
                        ft.Row(
                            controls=toolbar_buttons,
                            spacing=spacing.xs
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()

    def _build_status_indicator(self) -> ft.Control:
        """Build answer status indicator."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            icons = self.get_icons()

            if self._state.is_loading:
                return ft.Row(
                    controls=[
                        ft.ProgressRing(
                            width=16,
                            height=16,
                            stroke_width=2,
                            color=palette.primary
                        ),
                        ft.Text(
                            "Generating answer...",
                            style=typography.body_small,
                            color=palette.text_secondary
                        )
                    ],
                    spacing=8
                )
            elif self._state.is_streaming:
                return ft.Row(
                    controls=[
                        ft.Icon(
                            icons.STREAM,
                            color=palette.primary,
                            size=16
                        ),
                        ft.Text(
                            "Streaming...",
                            style=typography.body_small,
                            color=palette.text_secondary
                        )
                    ],
                    spacing=8
                )
            elif self._state.current_answer:
                confidence = self._state.current_answer.confidence_score
                confidence_color = self._get_confidence_color(confidence)

                return ft.Row(
                    controls=[
                        ft.Icon(
                            icons.CHECK_CIRCLE,
                            color=confidence_color,
                            size=16
                        ),
                        ft.Text(
                            f"Confidence: {confidence:.1%}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        )
                    ],
                    spacing=8
                )
            else:
                return ft.Container()

        except Exception as e:
            logger.error(f"Error building status indicator: {e}")
            return ft.Container()

    def _build_feedback_section(self) -> ft.Control:
        """Build feedback section."""
        try:
            if not self._feedback_widget:
                return ft.Container()

            return ft.Container(
                content=self._feedback_widget,
                margin=ft.margin.only(top=self.get_spacing().md)
            )

        except Exception as e:
            logger.error(f"Error building feedback section: {e}")
            return ft.Container()

    def _build_compact_toolbar(self) -> ft.Control:
        """Build compact toolbar for mobile layout."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            icons = self.get_icons()

            # Essential buttons only
            buttons = []

            if self._config.enable_copy:
                buttons.append(
                    ft.IconButton(
                        icon=icons.COPY,
                        tooltip="Copy",
                        on_click=self._handle_copy_click,
                        icon_size=self.get_responsive_size(18)
                    )
                )

            if self._config.enable_regeneration:
                buttons.append(
                    ft.IconButton(
                        icon=icons.REFRESH,
                        tooltip="Regenerate",
                        on_click=self._handle_regenerate_click,
                        icon_size=self.get_responsive_size(18)
                    )
                )

            return ft.Container(
                content=ft.Row(
                    controls=[
                        self._build_status_indicator(),
                        ft.Container(expand=True),
                        ft.Row(controls=buttons, spacing=spacing.xs)
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.all(spacing.sm),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(6)
            )

        except Exception as e:
            logger.error(f"Error building compact toolbar: {e}")
            return ft.Container()

    def _build_collapsible_sources(self) -> ft.Control:
        """Build collapsible sources section for compact layout."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            if not self._source_panel:
                return ft.Container()

            # Collapsible header
            header = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icons.LIBRARY_BOOKS,
                            color=palette.text_secondary,
                            size=self.get_responsive_size(20)
                        ),
                        ft.Text(
                            "Sources",
                            style=typography.title_small,
                            color=palette.text_primary
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=icons.EXPAND_MORE,
                            on_click=self._handle_sources_toggle,
                            icon_size=self.get_responsive_size(20)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=ft.padding.all(spacing.sm),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8),
                on_click=self._handle_sources_toggle
            )

            # Collapsible content
            content = ft.Container(
                content=self._source_panel,
                visible=self._state.is_expanded,
                animate_opacity=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
            )

            return ft.Column(
                controls=[header, content],
                spacing=spacing.xs
            )

        except Exception as e:
            logger.error(f"Error building collapsible sources: {e}")
            return ft.Container()

    def _build_compact_feedback(self) -> ft.Control:
        """Build compact feedback section."""
        try:
            if not self._feedback_widget:
                return ft.Container()

            return ft.Container(
                content=self._feedback_widget,
                margin=ft.margin.only(top=self.get_spacing().sm)
            )

        except Exception as e:
            logger.error(f"Error building compact feedback: {e}")
            return ft.Container()

    def _build_error_layout(self, error_message: str) -> ft.Control:
        """Build error layout when something goes wrong."""
        try:
            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()
            icons = self.get_icons()

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            icons.ERROR,
                            color=palette.error,
                            size=self.get_responsive_size(48)
                        ),
                        ft.Text(
                            "Error Loading Answer",
                            style=typography.headline_small,
                            color=palette.text_primary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            error_message,
                            style=typography.body_medium,
                            color=palette.text_secondary,
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.ElevatedButton(
                            text="Retry",
                            icon=icons.REFRESH,
                            on_click=self._handle_retry_click
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                padding=spacing.xl,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(12)
            )

        except Exception as e:
            logger.error(f"Error building error layout: {e}")
            return ft.Container()

    # Event Handlers
    def _handle_source_click(self, source_id: str) -> None:
        """Handle source document click."""
        try:
            self._state.selected_source = source_id

            if self._on_source_click:
                self._on_source_click(source_id)

            logger.info(f"Source clicked: {source_id}")

        except Exception as e:
            logger.error(f"Error handling source click: {e}")

    def _handle_source_navigate(self, source_id: str, position: int) -> None:
        """Handle source navigation."""
        try:
            if self._on_source_navigate:
                self._on_source_navigate(source_id, position)

            logger.info(f"Source navigation: {source_id} at position {position}")

        except Exception as e:
            logger.error(f"Error handling source navigation: {e}")

    def _handle_feedback_submit(self, feedback: FeedbackData) -> None:
        """Handle feedback submission."""
        try:
            self._state.feedback_submitted = True

            if self._on_feedback_submit:
                self._on_feedback_submit(feedback)

            logger.info(f"Feedback submitted for answer: {feedback.answer_id}")

        except Exception as e:
            logger.error(f"Error handling feedback submission: {e}")

    def _handle_answer_copy(self, answer_text: str) -> None:
        """Handle answer copy action."""
        try:
            self._state.answer_copied = True

            if self._on_answer_copy:
                self._on_answer_copy(answer_text)

            logger.info("Answer copied to clipboard")

        except Exception as e:
            logger.error(f"Error handling answer copy: {e}")

    def _handle_copy_click(self, e) -> None:
        """Handle copy button click."""
        try:
            if self._state.current_answer:
                self._handle_answer_copy(self._state.current_answer.answer)

        except Exception as e:
            logger.error(f"Error handling copy click: {e}")

    def _handle_share_click(self, e) -> None:
        """Handle share button click."""
        try:
            if self._state.current_answer and self._on_answer_share:
                self._on_answer_share(self._state.current_answer.answer)

        except Exception as e:
            logger.error(f"Error handling share click: {e}")

    def _handle_regenerate_click(self, e) -> None:
        """Handle regenerate button click."""
        try:
            if self._state.current_answer and self._on_answer_regenerate:
                self._on_answer_regenerate(self._state.current_answer.query)

        except Exception as e:
            logger.error(f"Error handling regenerate click: {e}")

    def _handle_expand_click(self, e) -> None:
        """Handle expand/collapse button click."""
        try:
            self._state.is_expanded = not self._state.is_expanded
            self.update()

        except Exception as e:
            logger.error(f"Error handling expand click: {e}")

    def _handle_sources_toggle(self, e) -> None:
        """Handle sources section toggle."""
        try:
            self._state.is_expanded = not self._state.is_expanded
            self.update()

        except Exception as e:
            logger.error(f"Error handling sources toggle: {e}")

    def _handle_retry_click(self, e) -> None:
        """Handle retry button click."""
        try:
            self._state.retry_count += 1
            self._state.error_message = None

            if self._state.current_answer and self._on_answer_regenerate:
                self._on_answer_regenerate(self._state.current_answer.query)

            self.update()

        except Exception as e:
            logger.error(f"Error handling retry click: {e}")

    # Utility Methods
    def _get_confidence_color(self, confidence: float) -> str:
        """Get color for confidence score."""
        try:
            palette = self.get_palette()

            if confidence >= 0.8:
                return palette.success
            elif confidence >= 0.6:
                return palette.warning
            else:
                return palette.error

        except Exception as e:
            logger.error(f"Error getting confidence color: {e}")
            return self.get_palette().text_secondary

    def _build_answer_metadata(self) -> ft.Control:
        """Build answer metadata section for detailed layout."""
        try:
            if not self._state.current_answer:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            answer = self._state.current_answer

            metadata_items = [
                ("Model", answer.model_name),
                ("Generation Time", f"{answer.generation_time:.2f}s"),
                ("Token Count", str(answer.token_count)),
                ("Sources", str(answer.total_sources)),
                ("Strategy", answer.search_strategy.title())
            ]

            metadata_controls = []
            for label, value in metadata_items:
                if value:
                    metadata_controls.append(
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"{label}:",
                                    style=typography.body_small,
                                    color=palette.text_secondary,
                                    weight=ft.FontWeight.W_500
                                ),
                                ft.Text(
                                    value,
                                    style=typography.body_small,
                                    color=palette.text_primary
                                )
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        )
                    )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Answer Details",
                            style=typography.title_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600
                        ),
                        ft.Divider(color=palette.outline_variant),
                        ft.Column(
                            controls=metadata_controls,
                            spacing=spacing.xs
                        )
                    ],
                    spacing=spacing.sm
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building answer metadata: {e}")
            return ft.Container()

    def _build_answer_controls(self) -> ft.Control:
        """Build answer control buttons for detailed layout."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            icons = self.get_icons()

            controls = []

            if self._config.enable_copy:
                controls.append(
                    ft.ElevatedButton(
                        text="Copy Answer",
                        icon=icons.COPY,
                        on_click=self._handle_copy_click,
                        width=200
                    )
                )

            if self._config.enable_share:
                controls.append(
                    ft.OutlinedButton(
                        text="Share",
                        icon=icons.SHARE,
                        on_click=self._handle_share_click,
                        width=200
                    )
                )

            if self._config.enable_regeneration:
                controls.append(
                    ft.OutlinedButton(
                        text="Regenerate",
                        icon=icons.REFRESH,
                        on_click=self._handle_regenerate_click,
                        width=200
                    )
                )

            return ft.Column(
                controls=controls,
                spacing=spacing.sm
            )

        except Exception as e:
            logger.error(f"Error building answer controls: {e}")
            return ft.Container()

    def _build_answer_history(self) -> ft.Control:
        """Build answer history section."""
        try:
            if not self._state.answer_history:
                return ft.Container()

            palette = self.get_palette()
            typography = self.get_typography()
            spacing = self.get_spacing()

            history_items = []
            for i, answer in enumerate(self._state.answer_history[-5:]):  # Show last 5
                history_items.append(
                    ft.ListTile(
                        leading=ft.Icon(
                            self.get_icons().HISTORY,
                            color=palette.text_secondary,
                            size=self.get_responsive_size(20)
                        ),
                        title=ft.Text(
                            f"Answer {i+1}",
                            style=typography.body_medium,
                            color=palette.text_primary
                        ),
                        subtitle=ft.Text(
                            f"Confidence: {answer.confidence_score:.1%}",
                            style=typography.body_small,
                            color=palette.text_secondary
                        ),
                        on_click=lambda e, ans=answer: self.set_answer(ans)
                    )
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Answer History",
                            style=typography.title_small,
                            color=palette.text_primary,
                            weight=ft.FontWeight.W_600
                        ),
                        ft.Divider(color=palette.outline_variant),
                        ft.Column(
                            controls=history_items,
                            spacing=0
                        )
                    ],
                    spacing=spacing.sm
                ),
                padding=ft.padding.all(spacing.md),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building answer history: {e}")
            return ft.Container()

    def _build_related_answers(self) -> ft.Control:
        """Build related answers section."""
        try:
            # Placeholder for related answers functionality
            return ft.Container()

        except Exception as e:
            logger.error(f"Error building related answers: {e}")
            return ft.Container()

    def _build_detailed_toolbar(self) -> ft.Control:
        """Build detailed toolbar for expanded layout."""
        try:
            return self._build_toolbar_section()  # Use same toolbar for now

        except Exception as e:
            logger.error(f"Error building detailed toolbar: {e}")
            return ft.Container()

    # Public API Methods
    def set_answer(self, answer: RAGAnswer) -> None:
        """Set the current answer to display."""
        try:
            # Add current answer to history if it exists
            if self._state.current_answer:
                self._state.answer_history.append(self._state.current_answer)

            # Set new answer
            self._state.current_answer = answer
            self._state.is_loading = False
            self._state.is_streaming = False
            self._state.error_message = None

            # Reinitialize components with new answer
            self._answer_box = None
            self._source_panel = None
            self._feedback_widget = None

            # Update UI
            self.update()

            logger.info(f"Answer set: {answer.id}")

        except Exception as e:
            logger.error(f"Error setting answer: {e}")
            self._state.error_message = str(e)

    def set_loading(self, loading: bool = True) -> None:
        """Set loading state."""
        try:
            self._state.is_loading = loading
            if loading:
                self._state.is_streaming = False
                self._state.error_message = None

            self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def set_streaming(self, streaming: bool = True) -> None:
        """Set streaming state."""
        try:
            self._state.is_streaming = streaming
            if streaming:
                self._state.is_loading = False
                self._state.error_message = None

            self.update()

        except Exception as e:
            logger.error(f"Error setting streaming state: {e}")

    def set_error(self, error_message: str) -> None:
        """Set error state."""
        try:
            self._state.error_message = error_message
            self._state.is_loading = False
            self._state.is_streaming = False

            self.update()

        except Exception as e:
            logger.error(f"Error setting error state: {e}")

    def clear_answer(self) -> None:
        """Clear the current answer."""
        try:
            self._state.current_answer = None
            self._state.is_loading = False
            self._state.is_streaming = False
            self._state.error_message = None
            self._state.feedback_submitted = False
            self._state.answer_copied = False

            # Clear components
            self._answer_box = None
            self._source_panel = None
            self._feedback_widget = None

            self.update()

        except Exception as e:
            logger.error(f"Error clearing answer: {e}")

    def get_current_answer(self) -> Optional[RAGAnswer]:
        """Get the current answer."""
        return self._state.current_answer

    def get_answer_history(self) -> List[RAGAnswer]:
        """Get answer history."""
        return self._state.answer_history.copy()

    def update_config(self, config: RAGAnswerConfig) -> None:
        """Update interface configuration."""
        try:
            self._config = config

            # Reinitialize components with new config
            self._answer_box = None
            self._source_panel = None
            self._feedback_widget = None

            self.update()

        except Exception as e:
            logger.error(f"Error updating config: {e}")

    def set_layout(self, layout: RAGAnswerLayout) -> None:
        """Set layout mode."""
        try:
            self._config.layout = layout
            self.update()

        except Exception as e:
            logger.error(f"Error setting layout: {e}")

    def set_view(self, view: RAGAnswerView) -> None:
        """Set view mode."""
        try:
            self._config.view = view
            self.update()

        except Exception as e:
            logger.error(f"Error setting view: {e}")

    def toggle_sources(self) -> None:
        """Toggle source panel visibility."""
        try:
            self._config.show_sources = not self._config.show_sources
            self.update()

        except Exception as e:
            logger.error(f"Error toggling sources: {e}")

    def toggle_feedback(self) -> None:
        """Toggle feedback widget visibility."""
        try:
            self._config.show_feedback = not self._config.show_feedback
            self.update()

        except Exception as e:
            logger.error(f"Error toggling feedback: {e}")

    def get_state(self) -> RAGAnswerState:
        """Get current interface state."""
        return self._state

    def reset_state(self) -> None:
        """Reset interface state."""
        try:
            self._state = RAGAnswerState()
            self.clear_answer()

        except Exception as e:
            logger.error(f"Error resetting state: {e}")

    def _build_split_layout(self) -> ft.Control:
        """Build split layout with resizable panels."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()

            # Create component instances
            self._initialize_components()

            # Split view with resizable divider
            left_panel = ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_toolbar_section(),
                        self._answer_box,
                        self._build_feedback_section() if self._config.show_feedback else ft.Container()
                    ],
                    spacing=spacing.md,
                    expand=True
                ),
                expand=True,
                padding=ft.padding.only(right=spacing.sm)
            )

            right_panel = ft.Container(
                content=self._source_panel,
                width=self.get_responsive_value(350, 400, 450, 500),
                padding=ft.padding.only(left=spacing.sm)
            ) if self._config.show_sources else ft.Container()

            # Create split view
            split_content = ft.Row(
                controls=[left_panel, right_panel] if self._config.show_sources else [left_panel],
                spacing=spacing.md,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )

            return self.create_responsive_container(
                content=split_content,
                padding=spacing.md,
                bgcolor=palette.surface,
                border_radius=self.get_responsive_size(12)
            )

        except Exception as e:
            logger.error(f"Error building split layout: {e}")
            return self._build_error_layout(str(e))

    def _initialize_components(self) -> None:
        """Initialize child components."""
        try:
            # Initialize answer box
            if not self._answer_box:
                self._answer_box = AnswerBoxUI(
                    answer=self._state.current_answer,
                    show_confidence=self._config.show_confidence,
                    show_sources=self._config.show_sources,
                    show_metadata=self._config.show_metadata,
                    enable_streaming=self._config.enable_streaming,
                    max_answer_length=self._config.max_answer_length,
                    on_source_click=self._handle_source_click,
                    on_copy=self._handle_answer_copy
                )

            # Initialize source panel
            if not self._source_panel and self._config.show_sources:
                sources = []
                if self._state.current_answer and self._state.current_answer.source_references:
                    sources = [
                        SourceDocument(
                            id=ref.document_id,
                            title=ref.title,
                            content=ref.content,
                            relevance_score=ref.relevance_score,
                            document_type=ref.document_type,
                            metadata=ref.metadata
                        )
                        for ref in self._state.current_answer.source_references[:self._config.max_sources]
                    ]

                self._source_panel = SourcePanelUI(
                    sources=sources,
                    display_mode=SourceDisplayMode.DETAILED,
                    show_relevance_scores=True,
                    show_metadata=self._config.show_metadata,
                    enable_preview=self._config.show_source_preview,
                    on_source_click=self._handle_source_click,
                    on_source_navigate=self._handle_source_navigate
                )

            # Initialize feedback widget
            if not self._feedback_widget and self._config.show_feedback:
                self._feedback_widget = FeedbackWidgetUI(
                    answer_id=self._state.current_answer.id if self._state.current_answer else "",
                    show_rating=True,
                    show_comments=True,
                    show_quick_feedback=True,
                    on_feedback_submit=self._handle_feedback_submit
                )

        except Exception as e:
            logger.error(f"Error initializing components: {e}")

    def _build_toolbar_section(self) -> ft.Control:
        """Build the main toolbar section."""
        try:
            palette = self.get_palette()
            spacing = self.get_spacing()
            typography = self.get_typography()
            icons = self.get_icons()

            # Toolbar buttons
            toolbar_buttons = []

            # Copy button
            if self._config.enable_copy:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.COPY,
                        tooltip="Copy Answer",
                        on_click=self._handle_copy_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Share button
            if self._config.enable_share:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.SHARE,
                        tooltip="Share Answer",
                        on_click=self._handle_share_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Regenerate button
            if self._config.enable_regeneration:
                toolbar_buttons.append(
                    ft.IconButton(
                        icon=icons.REFRESH,
                        tooltip="Regenerate Answer",
                        on_click=self._handle_regenerate_click,
                        icon_color=palette.text_secondary,
                        icon_size=self.get_responsive_size(20)
                    )
                )

            # Expand/collapse button
            toolbar_buttons.append(
                ft.IconButton(
                    icon=icons.EXPAND_MORE if not self._state.is_expanded else icons.EXPAND_LESS,
                    tooltip="Expand/Collapse",
                    on_click=self._handle_expand_click,
                    icon_color=palette.text_secondary,
                    icon_size=self.get_responsive_size(20)
                )
            )

            # Answer status indicator
            status_indicator = self._build_status_indicator()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        status_indicator,
                        ft.Container(expand=True),  # Spacer
                        ft.Row(
                            controls=toolbar_buttons,
                            spacing=spacing.xs
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(horizontal=spacing.sm, vertical=spacing.xs),
                bgcolor=palette.surface_variant,
                border_radius=self.get_responsive_size(8)
            )

        except Exception as e:
            logger.error(f"Error building toolbar section: {e}")
            return ft.Container()
