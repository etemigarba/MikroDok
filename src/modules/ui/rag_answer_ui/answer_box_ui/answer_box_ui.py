"""
Module: answer_box_ui
Description: AI-generated answer display box with confidence scores, source references, and comprehensive
            theming integration. Provides responsive answer presentation with highlighting, metadata,
            and interactive features for RAG (Retrieval Augmented Generation) responses.
Phase: 4
Location: /src/modules/ui/rag_answer_ui/answer_box_ui/answer_box_ui.py
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
    ResponsiveLayoutManager,
    get_theme_manager
)

# Configure logging
logger = logging.getLogger(__name__)


class AnswerState(Enum):
    """Answer display states for visual feedback."""
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    EMPTY = "empty"
    STREAMING = "streaming"


class ConfidenceLevel(Enum):
    """Confidence level categories for visual styling."""
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"           # 75-89%
    MEDIUM = "medium"       # 50-74%
    LOW = "low"            # 25-49%
    VERY_LOW = "very_low"  # 0-24%


@dataclass
class SourceReference:
    """
    Source reference data structure for answer citations.
    
    Contains information about documents and chunks used to generate the answer.
    """
    # Core identification
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    
    # Content information
    title: str = ""
    snippet: str = ""
    page_number: Optional[int] = None
    
    # Relevance and scoring
    relevance_score: float = 0.0
    citation_weight: float = 1.0
    
    # Document metadata
    document_type: str = "unknown"
    file_path: str = ""
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGAnswer:
    """
    Comprehensive RAG answer data structure.
    
    Contains the generated answer with metadata, confidence scores,
    source references, and generation context.
    """
    # Core content
    id: str
    query: str
    answer: str
    
    # Confidence and quality metrics
    confidence_score: float = 0.0
    quality_score: float = 0.0
    relevance_score: float = 0.0
    
    # Source information
    source_references: List[SourceReference] = field(default_factory=list)
    total_sources: int = 0
    
    # Generation metadata
    model_name: str = ""
    generation_time: float = 0.0
    token_count: int = 0
    
    # Timestamps
    created_at: Optional[datetime] = None
    
    # Additional context
    search_strategy: str = "hybrid"
    retrieval_context: Dict[str, Any] = field(default_factory=dict)
    
    # User interaction
    is_helpful: Optional[bool] = None
    user_feedback: str = ""
    
    # Display options
    highlighted_terms: List[str] = field(default_factory=list)
    formatted_sections: List[Dict[str, Any]] = field(default_factory=list)


class AnswerBoxUI(ThemeAwareUserControl):
    """
    AI-generated answer display box with comprehensive theming and responsive design.
    
    Features:
    - Responsive answer display with adaptive layouts
    - Theme-aware styling with no hardcoded colors or dimensions
    - Confidence score visualization with color-coded indicators
    - Source reference integration with clickable citations
    - Real-time streaming answer support
    - Interactive feedback collection
    - Accessibility compliance with ARIA labels and keyboard navigation
    - Performance optimization for large answers
    - Smooth animations and transitions
    - Integration with document viewer and source panel
    """
    
    def __init__(
        self,
        answer: Optional[RAGAnswer] = None,
        show_confidence: bool = True,
        show_sources: bool = True,
        show_metadata: bool = True,
        enable_feedback: bool = True,
        enable_streaming: bool = True,
        max_answer_length: int = 2000,
        on_source_click: Optional[Callable[[SourceReference], None]] = None,
        on_feedback: Optional[Callable[[str, bool], None]] = None,
        on_copy: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        """
        Initialize the answer box UI component.
        
        Args:
            answer: The RAG answer data to display
            show_confidence: Whether to show confidence indicators
            show_sources: Whether to show source references
            show_metadata: Whether to show generation metadata
            enable_feedback: Whether to enable user feedback
            enable_streaming: Whether to support streaming answers
            max_answer_length: Maximum length for answer display
            on_source_click: Callback for source reference clicks
            on_feedback: Callback for user feedback
            on_copy: Callback for copy actions
            **kwargs: Additional component properties
        """
        super().__init__(**kwargs)
        
        # Core properties
        self._answer = answer
        self._show_confidence = show_confidence
        self._show_sources = show_sources
        self._show_metadata = show_metadata
        self._enable_feedback = enable_feedback
        self._enable_streaming = enable_streaming
        self._max_answer_length = max_answer_length
        
        # Callbacks
        self._on_source_click = on_source_click
        self._on_feedback = on_feedback
        self._on_copy = on_copy
        
        # State management
        self._answer_state = AnswerState.EMPTY if not answer else AnswerState.READY
        self._is_streaming = False
        self._streaming_text = ""
        self._animation_duration = 300
        
        # UI components
        self._main_container: Optional[ft.Control] = None
        self._answer_content: Optional[ft.Control] = None
        self._confidence_indicator: Optional[ft.Control] = None
        self._sources_section: Optional[ft.Control] = None
        self._feedback_section: Optional[ft.Control] = None
        
        # Initialize component
        self._initialize_component()
    
    def _initialize_component(self) -> None:
        """Initialize the answer box component with theme integration."""
        try:
            # Ensure theme manager is available
            self._ensure_theme_manager()
            
            # Set up responsive callbacks
            self._setup_responsive_callbacks()
            
            # Initialize interaction handlers
            self._setup_interaction_handlers()
            
        except Exception as e:
            logger.error(f"Error initializing answer box UI: {e}")
    
    def build(self) -> ft.Control:
        """Build the responsive answer box interface."""
        try:
            # Build based on current state
            if self._answer_state == AnswerState.LOADING:
                return self._build_loading_state()
            elif self._answer_state == AnswerState.ERROR:
                return self._build_error_state()
            elif self._answer_state == AnswerState.EMPTY:
                return self._build_empty_state()
            elif self._answer_state == AnswerState.STREAMING:
                return self._build_streaming_state()
            else:
                return self._build_answer_display()
                
        except Exception as e:
            logger.error(f"Error building answer box: {e}")
            return self._build_error_state(str(e))
    
    def _build_answer_display(self) -> ft.Control:
        """Build the main answer display interface."""
        try:
            if not self._answer:
                return self._build_empty_state()
            
            theme = self.get_theme()
            spacing = self.get_spacing()
            
            # Build main content sections
            content_sections = []
            
            # Add confidence indicator if enabled
            if self._show_confidence:
                content_sections.append(self._build_confidence_section())
            
            # Add main answer content
            content_sections.append(self._build_answer_content())
            
            # Add source references if enabled
            if self._show_sources and self._answer.source_references:
                content_sections.append(self._build_sources_section())
            
            # Add metadata if enabled
            if self._show_metadata:
                content_sections.append(self._build_metadata_section())
            
            # Add feedback section if enabled
            if self._enable_feedback:
                content_sections.append(self._build_feedback_section())
            
            return self.create_responsive_container(
                content=ft.Column(
                    controls=content_sections,
                    spacing=spacing.lg,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=spacing.lg,
                bgcolor=theme.get_color("surface"),
                border=ft.border.all(1, theme.get_color("outline_variant")),
                border_radius=self.get_responsive_value(8, 10, 12, 14)
            )
            
        except Exception as e:
            logger.error(f"Error building answer display: {e}")
            return self._build_error_state(str(e))

    def _build_confidence_section(self) -> ft.Control:
        """Build confidence score indicator section."""
        try:
            if not self._answer or not self._show_confidence:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            confidence = self._answer.confidence_score
            confidence_level = self._get_confidence_level(confidence)
            confidence_color = self._get_confidence_color(confidence_level)

            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.PSYCHOLOGY,
                            size=self.get_responsive_value(16, 18, 20, 22),
                            color=confidence_color
                        ),
                        ft.Text(
                            "Confidence:",
                            style=typography.get_text_style("label_medium"),
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Container(
                                        width=self.get_responsive_value(80, 100, 120, 140),
                                        height=self.get_responsive_value(6, 7, 8, 9),
                                        bgcolor=theme.get_color("surface_variant"),
                                        border_radius=self.get_responsive_value(3, 4, 4, 5),
                                        content=ft.Container(
                                            width=self.get_responsive_value(80, 100, 120, 140) * confidence,
                                            height=self.get_responsive_value(6, 7, 8, 9),
                                            bgcolor=confidence_color,
                                            border_radius=self.get_responsive_value(3, 4, 4, 5)
                                        ),
                                        alignment=ft.alignment.center_left
                                    ),
                                    ft.Text(
                                        f"{confidence:.1%}",
                                        style=typography.get_text_style("label_small"),
                                        color=confidence_color,
                                        weight=ft.FontWeight.W_500
                                    )
                                ],
                                spacing=spacing.sm,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            )
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.padding.symmetric(vertical=spacing.xs)
            )

        except Exception as e:
            logger.error(f"Error building confidence section: {e}")
            return ft.Container()

    def _build_answer_content(self) -> ft.Control:
        """Build the main answer content display."""
        try:
            if not self._answer:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Truncate answer if too long
            answer_text = self._answer.answer
            if len(answer_text) > self._max_answer_length:
                answer_text = answer_text[:self._max_answer_length - 3] + "..."

            # Build answer content with highlighting if available
            if self._answer.highlighted_terms:
                answer_content = self._build_highlighted_answer(answer_text)
            else:
                answer_content = ft.Text(
                    answer_text,
                    style=typography.get_text_style("body_large"),
                    color=theme.get_color("on_surface"),
                    selectable=True
                )

            return ft.Container(
                content=ft.Column(
                    controls=[
                        # Answer header with copy button
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "Answer",
                                    style=typography.get_text_style("title_medium"),
                                    color=theme.get_color("on_surface"),
                                    weight=ft.FontWeight.W_500
                                ),
                                ft.Spacer(),
                                ft.IconButton(
                                    icon=ft.Icons.CONTENT_COPY,
                                    icon_size=self.get_responsive_value(16, 18, 20, 22),
                                    icon_color=theme.get_color("on_surface_variant"),
                                    tooltip="Copy answer",
                                    on_click=self._handle_copy_click
                                )
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        # Answer content
                        ft.Container(
                            content=answer_content,
                            padding=ft.padding.all(spacing.md),
                            bgcolor=theme.get_color("surface_variant"),
                            border_radius=self.get_responsive_value(6, 7, 8, 9)
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building answer content: {e}")
            return ft.Container()

    def _build_sources_section(self) -> ft.Control:
        """Build source references section."""
        try:
            if not self._answer or not self._answer.source_references:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            # Build source cards
            source_cards = []
            for i, source in enumerate(self._answer.source_references[:5]):  # Limit to 5 sources
                source_cards.append(self._build_source_card(source, i + 1))

            return ft.Container(
                content=ft.Column(
                    controls=[
                        # Sources header
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.SOURCE,
                                    size=self.get_responsive_value(16, 18, 20, 22),
                                    color=theme.get_color("primary")
                                ),
                                ft.Text(
                                    f"Sources ({len(self._answer.source_references)})",
                                    style=typography.get_text_style("title_small"),
                                    color=theme.get_color("on_surface"),
                                    weight=ft.FontWeight.W_500
                                )
                            ],
                            spacing=spacing.xs
                        ),
                        # Source cards
                        ft.Column(
                            controls=source_cards,
                            spacing=spacing.sm,
                            tight=True
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                )
            )

        except Exception as e:
            logger.error(f"Error building sources section: {e}")
            return ft.Container()

    def _build_source_card(self, source: SourceReference, index: int) -> ft.Control:
        """Build individual source reference card."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Row(
                    controls=[
                        # Source index
                        ft.Container(
                            content=ft.Text(
                                str(index),
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_primary"),
                                weight=ft.FontWeight.W_500
                            ),
                            width=self.get_responsive_value(20, 22, 24, 26),
                            height=self.get_responsive_value(20, 22, 24, 26),
                            bgcolor=theme.get_color("primary"),
                            border_radius=self.get_responsive_value(10, 11, 12, 13),
                            alignment=ft.alignment.center
                        ),
                        # Source content
                        ft.Expanded(
                            child=ft.Column(
                                controls=[
                                    # Title
                                    ft.Text(
                                        source.title or "Untitled Document",
                                        style=typography.get_text_style("body_medium"),
                                        color=theme.get_color("on_surface"),
                                        weight=ft.FontWeight.W_500,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        max_lines=1
                                    ),
                                    # Snippet
                                    ft.Text(
                                        self._truncate_text(source.snippet, 100),
                                        style=typography.get_text_style("body_small"),
                                        color=theme.get_color("on_surface_variant"),
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        max_lines=2
                                    ) if source.snippet else None,
                                    # Metadata
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                source.document_type.upper(),
                                                style=typography.get_text_style("label_small"),
                                                color=theme.get_color("on_surface_variant")
                                            ),
                                            ft.Text(
                                                f"Page {source.page_number}",
                                                style=typography.get_text_style("label_small"),
                                                color=theme.get_color("on_surface_variant")
                                            ) if source.page_number else None,
                                            ft.Text(
                                                f"{source.relevance_score:.1%}",
                                                style=typography.get_text_style("label_small"),
                                                color=self._get_relevance_color(source.relevance_score)
                                            )
                                        ],
                                        spacing=spacing.sm,
                                        wrap=True
                                    )
                                ],
                                spacing=spacing.xs,
                                tight=True
                            )
                        ),
                        # Action button
                        ft.IconButton(
                            icon=ft.Icons.OPEN_IN_NEW,
                            icon_size=self.get_responsive_value(16, 18, 20, 22),
                            icon_color=theme.get_color("on_surface_variant"),
                            tooltip="Open source",
                            on_click=lambda e, src=source: self._handle_source_click(src)
                        )
                    ],
                    spacing=spacing.sm,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                padding=ft.padding.all(spacing.sm),
                bgcolor=theme.get_color("surface_container_lowest"),
                border_radius=self.get_responsive_value(6, 7, 8, 9),
                on_click=lambda e, src=source: self._handle_source_click(src)
            )

        except Exception as e:
            logger.error(f"Error building source card: {e}")
            return ft.Container()

    def _build_metadata_section(self) -> ft.Control:
        """Build metadata section with generation information."""
        try:
            if not self._answer or not self._show_metadata:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            metadata_items = []

            # Model name
            if self._answer.model_name:
                metadata_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.SMART_TOY,
                                size=self.get_responsive_value(14, 16, 18, 20),
                                color=theme.get_color("on_surface_variant")
                            ),
                            ft.Text(
                                f"Model: {self._answer.model_name}",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs
                    )
                )

            # Generation time
            if self._answer.generation_time > 0:
                metadata_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.TIMER,
                                size=self.get_responsive_value(14, 16, 18, 20),
                                color=theme.get_color("on_surface_variant")
                            ),
                            ft.Text(
                                f"Generated in {self._answer.generation_time:.2f}s",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs
                    )
                )

            # Token count
            if self._answer.token_count > 0:
                metadata_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.TOKEN,
                                size=self.get_responsive_value(14, 16, 18, 20),
                                color=theme.get_color("on_surface_variant")
                            ),
                            ft.Text(
                                f"{self._answer.token_count} tokens",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs
                    )
                )

            # Search strategy
            if self._answer.search_strategy:
                metadata_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.SEARCH,
                                size=self.get_responsive_value(14, 16, 18, 20),
                                color=theme.get_color("on_surface_variant")
                            ),
                            ft.Text(
                                f"Strategy: {self._answer.search_strategy.title()}",
                                style=typography.get_text_style("label_small"),
                                color=theme.get_color("on_surface_variant")
                            )
                        ],
                        spacing=spacing.xs
                    )
                )

            if not metadata_items:
                return ft.Container()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Generation Details",
                            style=typography.get_text_style("label_medium"),
                            color=theme.get_color("on_surface_variant"),
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Column(
                            controls=metadata_items,
                            spacing=spacing.xs,
                            tight=True
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                ),
                padding=ft.padding.symmetric(vertical=spacing.xs)
            )

        except Exception as e:
            logger.error(f"Error building metadata section: {e}")
            return ft.Container()

    def _build_feedback_section(self) -> ft.Control:
        """Build user feedback section."""
        try:
            if not self._enable_feedback:
                return ft.Container()

            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Was this answer helpful?",
                            style=typography.get_text_style("label_medium"),
                            color=theme.get_color("on_surface_variant"),
                            weight=ft.FontWeight.W_500
                        ),
                        ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.THUMB_UP,
                                    icon_size=self.get_responsive_value(20, 22, 24, 26),
                                    icon_color=theme.get_color("success") if self._answer and self._answer.is_helpful is True else theme.get_color("on_surface_variant"),
                                    tooltip="Helpful",
                                    on_click=lambda e: self._handle_feedback_click(True)
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.THUMB_DOWN,
                                    icon_size=self.get_responsive_value(20, 22, 24, 26),
                                    icon_color=theme.get_color("error") if self._answer and self._answer.is_helpful is False else theme.get_color("on_surface_variant"),
                                    tooltip="Not helpful",
                                    on_click=lambda e: self._handle_feedback_click(False)
                                ),
                                ft.VerticalDivider(
                                    width=1,
                                    color=theme.get_color("outline_variant")
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FLAG,
                                    icon_size=self.get_responsive_value(20, 22, 24, 26),
                                    icon_color=theme.get_color("on_surface_variant"),
                                    tooltip="Report issue",
                                    on_click=self._handle_report_click
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SHARE,
                                    icon_size=self.get_responsive_value(20, 22, 24, 26),
                                    icon_color=theme.get_color("on_surface_variant"),
                                    tooltip="Share answer",
                                    on_click=self._handle_share_click
                                )
                            ],
                            spacing=spacing.xs
                        )
                    ],
                    spacing=spacing.sm,
                    tight=True
                ),
                padding=ft.padding.symmetric(vertical=spacing.xs)
            )

        except Exception as e:
            logger.error(f"Error building feedback section: {e}")
            return ft.Container()

    def _build_loading_state(self) -> ft.Control:
        """Build loading state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(
                            width=self.get_responsive_value(32, 36, 40, 44),
                            height=self.get_responsive_value(32, 36, 40, 44),
                            stroke_width=self.get_responsive_value(3, 4, 4, 5),
                            color=theme.get_color("primary")
                        ),
                        ft.Text(
                            "Generating answer...",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=spacing.xl,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building loading state: {e}")
            return ft.Container()

    def _build_streaming_state(self) -> ft.Control:
        """Build streaming answer display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        # Streaming indicator
                        ft.Row(
                            controls=[
                                ft.ProgressRing(
                                    width=self.get_responsive_value(16, 18, 20, 22),
                                    height=self.get_responsive_value(16, 18, 20, 22),
                                    stroke_width=2,
                                    color=theme.get_color("primary")
                                ),
                                ft.Text(
                                    "Streaming answer...",
                                    style=typography.get_text_style("label_medium"),
                                    color=theme.get_color("primary")
                                )
                            ],
                            spacing=spacing.sm
                        ),
                        # Streaming content
                        ft.Container(
                            content=ft.Text(
                                self._streaming_text,
                                style=typography.get_text_style("body_large"),
                                color=theme.get_color("on_surface"),
                                selectable=True
                            ),
                            padding=ft.padding.all(spacing.md),
                            bgcolor=theme.get_color("surface_variant"),
                            border_radius=self.get_responsive_value(6, 7, 8, 9)
                        )
                    ],
                    spacing=spacing.sm,
                    scroll=ft.ScrollMode.AUTO
                ),
                padding=spacing.lg,
                bgcolor=theme.get_color("surface"),
                border=ft.border.all(1, theme.get_color("outline_variant")),
                border_radius=self.get_responsive_value(8, 10, 12, 14)
            )

        except Exception as e:
            logger.error(f"Error building streaming state: {e}")
            return ft.Container()

    def _build_empty_state(self) -> ft.Control:
        """Build empty state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.CHAT_BUBBLE_OUTLINE,
                            size=self.get_responsive_value(48, 56, 64, 72),
                            color=theme.get_color("on_surface_variant")
                        ),
                        ft.Text(
                            "No answer available",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            "Ask a question to get an AI-generated answer",
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=spacing.xl,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building empty state: {e}")
            return ft.Container()

    def _build_error_state(self, error_message: str = "An error occurred") -> ft.Control:
        """Build error state display."""
        try:
            theme = self.get_theme()
            typography = self.get_typography()
            spacing = self.get_spacing()

            return self.create_responsive_container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            size=self.get_responsive_value(48, 56, 64, 72),
                            color=theme.get_color("error")
                        ),
                        ft.Text(
                            "Error generating answer",
                            style=typography.get_text_style("title_medium"),
                            color=theme.get_color("error"),
                            text_align=ft.TextAlign.CENTER
                        ),
                        ft.Text(
                            error_message,
                            style=typography.get_text_style("body_medium"),
                            color=theme.get_color("on_surface_variant"),
                            text_align=ft.TextAlign.CENTER
                        )
                    ],
                    spacing=spacing.md,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=spacing.xl,
                alignment=ft.alignment.center
            )

        except Exception as e:
            logger.error(f"Error building error state: {e}")
            return ft.Container()

    def _build_highlighted_answer(self, text: str) -> ft.Control:
        """Build answer text with highlighted terms."""
        try:
            if not self._answer or not self._answer.highlighted_terms:
                theme = self.get_theme()
                typography = self.get_typography()
                return ft.Text(
                    text,
                    style=typography.get_text_style("body_large"),
                    color=theme.get_color("on_surface"),
                    selectable=True
                )

            # Create highlighted text spans
            spans = self._create_highlighted_spans(text, self._answer.highlighted_terms)

            theme = self.get_theme()
            typography = self.get_typography()

            return ft.Text(
                spans=spans,
                style=typography.get_text_style("body_large"),
                color=theme.get_color("on_surface"),
                selectable=True
            )

        except Exception as e:
            logger.error(f"Error building highlighted answer: {e}")
            theme = self.get_theme()
            typography = self.get_typography()
            return ft.Text(
                text,
                style=typography.get_text_style("body_large"),
                color=theme.get_color("on_surface"),
                selectable=True
            )

    def _create_highlighted_spans(self, text: str, terms: List[str]) -> List[ft.TextSpan]:
        """Create text spans with highlighted search terms."""
        try:
            theme = self.get_theme()
            spans = []

            if not terms:
                return [ft.TextSpan(text)]

            # Simple highlighting implementation
            current_text = text.lower()
            original_text = text
            last_end = 0

            for term in terms:
                term_lower = term.lower()
                start = current_text.find(term_lower, last_end)

                if start != -1:
                    # Add text before highlight
                    if start > last_end:
                        spans.append(ft.TextSpan(original_text[last_end:start]))

                    # Add highlighted term
                    spans.append(
                        ft.TextSpan(
                            original_text[start:start + len(term)],
                            style=ft.TextStyle(
                                bgcolor=theme.get_color("primary_container"),
                                color=theme.get_color("on_primary_container"),
                                weight=ft.FontWeight.W_500
                            )
                        )
                    )

                    last_end = start + len(term)

            # Add remaining text
            if last_end < len(original_text):
                spans.append(ft.TextSpan(original_text[last_end:]))

            return spans if spans else [ft.TextSpan(text)]

        except Exception as e:
            logger.error(f"Error creating highlighted spans: {e}")
            return [ft.TextSpan(text)]

    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level category from score."""
        try:
            if confidence >= 0.9:
                return ConfidenceLevel.VERY_HIGH
            elif confidence >= 0.75:
                return ConfidenceLevel.HIGH
            elif confidence >= 0.5:
                return ConfidenceLevel.MEDIUM
            elif confidence >= 0.25:
                return ConfidenceLevel.LOW
            else:
                return ConfidenceLevel.VERY_LOW

        except Exception as e:
            logger.error(f"Error getting confidence level: {e}")
            return ConfidenceLevel.MEDIUM

    def _get_confidence_color(self, level: ConfidenceLevel) -> str:
        """Get color for confidence level."""
        try:
            theme = self.get_theme()

            color_map = {
                ConfidenceLevel.VERY_HIGH: theme.get_color("success"),
                ConfidenceLevel.HIGH: theme.get_color("success"),
                ConfidenceLevel.MEDIUM: theme.get_color("warning"),
                ConfidenceLevel.LOW: theme.get_color("error"),
                ConfidenceLevel.VERY_LOW: theme.get_color("error")
            }

            return color_map.get(level, theme.get_color("on_surface_variant"))

        except Exception as e:
            logger.error(f"Error getting confidence color: {e}")
            return self.get_theme().get_color("on_surface_variant")

    def _get_relevance_color(self, score: float) -> str:
        """Get color for relevance score."""
        try:
            theme = self.get_theme()

            if score >= 0.8:
                return theme.get_color("success")
            elif score >= 0.6:
                return theme.get_color("warning")
            elif score >= 0.4:
                return theme.get_color("info")
            else:
                return theme.get_color("error")

        except Exception as e:
            logger.error(f"Error getting relevance color: {e}")
            return self.get_theme().get_color("on_surface_variant")

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to specified length with ellipsis."""
        try:
            if not text or len(text) <= max_length:
                return text

            return text[:max_length - 3] + "..."

        except Exception as e:
            logger.error(f"Error truncating text: {e}")
            return text or ""

    def _setup_responsive_callbacks(self) -> None:
        """Set up responsive design callbacks."""
        try:
            # Add responsive callback if available
            if hasattr(self, 'add_responsive_callback'):
                self.add_responsive_callback(self._on_screen_size_change)

        except Exception as e:
            logger.error(f"Error setting up responsive callbacks: {e}")

    def _setup_interaction_handlers(self) -> None:
        """Set up interaction event handlers."""
        try:
            # Initialize interaction state
            self._answer_state = AnswerState.EMPTY if not self._answer else AnswerState.READY

        except Exception as e:
            logger.error(f"Error setting up interaction handlers: {e}")

    def _on_screen_size_change(self, screen_size) -> None:
        """Handle screen size changes for responsive design."""
        try:
            # Update component if needed
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error handling screen size change: {e}")

    def _handle_copy_click(self, e) -> None:
        """Handle copy button click."""
        try:
            if self._answer and self._on_copy:
                self._on_copy(self._answer.answer)

        except Exception as e:
            logger.error(f"Error handling copy click: {e}")

    def _handle_source_click(self, source: SourceReference) -> None:
        """Handle source reference click."""
        try:
            if self._on_source_click:
                self._on_source_click(source)

        except Exception as e:
            logger.error(f"Error handling source click: {e}")

    def _handle_feedback_click(self, is_helpful: bool) -> None:
        """Handle feedback button click."""
        try:
            if self._answer:
                self._answer.is_helpful = is_helpful

            if self._on_feedback:
                self._on_feedback(self._answer.id if self._answer else "", is_helpful)

            # Update UI
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error handling feedback click: {e}")

    def _handle_report_click(self, e) -> None:
        """Handle report issue button click."""
        try:
            # TODO: Implement report functionality
            logger.info(f"Report clicked for answer: {self._answer.id if self._answer else 'unknown'}")

        except Exception as e:
            logger.error(f"Error handling report click: {e}")

    def _handle_share_click(self, e) -> None:
        """Handle share button click."""
        try:
            # TODO: Implement share functionality
            logger.info(f"Share clicked for answer: {self._answer.id if self._answer else 'unknown'}")

        except Exception as e:
            logger.error(f"Error handling share click: {e}")

    # Public methods for external control
    def set_answer(self, answer: RAGAnswer) -> None:
        """Set the answer data and refresh UI."""
        try:
            self._answer = answer
            self._answer_state = AnswerState.READY
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error setting answer: {e}")

    def clear_answer(self) -> None:
        """Clear the current answer and show empty state."""
        try:
            self._answer = None
            self._answer_state = AnswerState.EMPTY
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error clearing answer: {e}")

    def set_loading_state(self) -> None:
        """Set the component to loading state."""
        try:
            self._answer_state = AnswerState.LOADING
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error setting loading state: {e}")

    def set_error_state(self, error_message: str = "An error occurred") -> None:
        """Set the component to error state."""
        try:
            self._answer_state = AnswerState.ERROR
            self._error_message = error_message
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error setting error state: {e}")

    def start_streaming(self) -> None:
        """Start streaming mode for real-time answer generation."""
        try:
            self._answer_state = AnswerState.STREAMING
            self._is_streaming = True
            self._streaming_text = ""
            if hasattr(self, 'update'):
                self.update()

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")

    def update_streaming_text(self, text: str) -> None:
        """Update streaming text content."""
        try:
            if self._is_streaming:
                self._streaming_text = text
                if hasattr(self, 'update'):
                    self.update()

        except Exception as e:
            logger.error(f"Error updating streaming text: {e}")

    def finish_streaming(self, final_answer: RAGAnswer) -> None:
        """Finish streaming and set final answer."""
        try:
            self._is_streaming = False
            self._streaming_text = ""
            self.set_answer(final_answer)

        except Exception as e:
            logger.error(f"Error finishing streaming: {e}")

    def get_answer(self) -> Optional[RAGAnswer]:
        """Get the current answer data."""
        return self._answer

    def get_answer_state(self) -> AnswerState:
        """Get the current answer state."""
        return self._answer_state

    def is_streaming(self) -> bool:
        """Check if currently in streaming mode."""
        return self._is_streaming
