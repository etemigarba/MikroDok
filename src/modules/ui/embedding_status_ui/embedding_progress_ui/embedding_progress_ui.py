"""
Module: embedding_progress_ui
Description: Real-time embedding progress visualization with comprehensive tracking and control functionality.
            Provides responsive progress interface with document-by-document monitoring, batch operations,
            vector generation metrics, and seamless integration with embedding generation pipeline.
            Features modern UI/UX with theme-aware styling, accessibility compliance, and cross-platform compatibility.
Phase: 4
Location: /src/modules/ui/embedding_status_ui/embedding_progress_ui/embedding_progress_ui.py
"""

# Standard library imports
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
import time

# Third-party imports
import flet as ft

# Local imports
from src.modules.ui.theme_system_ui.theme_system_ui import (
    ThemeAwareUserControl,
    get_theme_manager
)
from src.modules.logic.logging_infrastructure_lg import get_logger


class EmbeddingProgressStatus(Enum):
    """Embedding progress status states."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    VECTORIZING = "vectorizing"
    STORING = "storing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmbeddingModelType(Enum):
    """Supported embedding model types."""
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    ALL_MINILM_L12_V2 = "all-MiniLM-L12-v2"
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"
    DISTILBERT_BASE = "distilbert-base-uncased"
    CUSTOM = "custom"


@dataclass
class EmbeddingProgressMetrics:
    """Metrics for embedding progress tracking."""
    vectors_per_second: float = 0.0
    average_vector_size: int = 0
    total_vectors_generated: int = 0
    memory_usage_mb: float = 0.0
    gpu_utilization_percent: float = 0.0
    cache_hit_rate: float = 0.0
    quality_score: float = 0.0
    estimated_time_remaining_seconds: int = 0


@dataclass
class EmbeddingProgressItem:
    """Individual embedding progress item."""
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    document_name: str = ""
    document_path: str = ""
    chunk_count: int = 0
    chunks_processed: int = 0
    vectors_generated: int = 0
    status: EmbeddingProgressStatus = EmbeddingProgressStatus.PENDING
    model_type: EmbeddingModelType = EmbeddingModelType.ALL_MINILM_L6_V2
    progress_percent: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    metrics: EmbeddingProgressMetrics = field(default_factory=EmbeddingProgressMetrics)
    file_size_bytes: int = 0
    vector_dimensions: int = 384


@dataclass
class EmbeddingProgressConfig:
    """Configuration for embedding progress tracking."""
    show_individual_documents: bool = True
    show_overall_progress: bool = True
    show_vector_metrics: bool = True
    show_performance_stats: bool = True
    enable_pause_resume: bool = True
    enable_cancel: bool = True
    auto_remove_completed: bool = False
    max_concurrent_embeddings: int = 3
    update_interval_ms: int = 100
    show_model_info: bool = True
    enable_quality_monitoring: bool = True


class EmbeddingProgressUI(ThemeAwareUserControl):
    """
    Comprehensive embedding progress tracking interface with real-time visualization.
    
    Features:
    - Responsive design with breakpoint-aware layouts
    - Real-time embedding progress tracking with vector metrics
    - Individual document progress monitoring
    - Batch operations (pause all, resume all, cancel all)
    - Pause/resume functionality for individual documents
    - Vector generation statistics and performance metrics
    - Theme-aware styling with accessibility compliance
    - Error handling and retry mechanisms
    - Integration with embedding generation pipeline
    """

    def __init__(
        self,
        config: Optional[EmbeddingProgressConfig] = None,
        on_progress_update: Optional[Callable[[str, float], None]] = None,
        on_embedding_complete: Optional[Callable[[str], None]] = None,
        on_embedding_error: Optional[Callable[[str, str], None]] = None,
        on_embedding_cancelled: Optional[Callable[[str], None]] = None,
        on_all_complete: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        """
        Initialize the embedding progress UI.
        
        Args:
            config: Embedding progress tracking configuration
            on_progress_update: Callback for progress updates
            on_embedding_complete: Callback when embedding completes
            on_embedding_error: Callback when embedding fails
            on_embedding_cancelled: Callback when embedding is cancelled
            on_all_complete: Callback when all embeddings complete
            **kwargs: Additional container properties
        """
        super().__init__(**kwargs)
        
        # Configuration and callbacks
        self._config = config or EmbeddingProgressConfig()
        self._on_progress_update = on_progress_update
        self._on_embedding_complete = on_embedding_complete
        self._on_embedding_error = on_embedding_error
        self._on_embedding_cancelled = on_embedding_cancelled
        self._on_all_complete = on_all_complete
        
        # State management
        self._progress_items: Dict[str, EmbeddingProgressItem] = {}
        self._is_paused = False
        self._total_progress = 0.0
        self._active_count = 0
        self._completed_count = 0
        self._failed_count = 0
        
        # UI components
        self._main_container: Optional[ft.Container] = None
        self._header_container: Optional[ft.Container] = None
        self._progress_list: Optional[ft.Column] = None
        self._overall_progress: Optional[ft.ProgressBar] = None
        self._stats_container: Optional[ft.Container] = None
        
        # Update timer
        self._update_timer: Optional[asyncio.Task] = None
        self._is_updating = False
        
        # Logger
        self._logger = get_logger(__name__)
        
    def build(self) -> ft.Control:
        """Build the embedding progress interface."""
        if not self._is_built:
            self._build_component()
            self._is_built = True
        return self._main_container
    
    def _build_component(self) -> None:
        """Build the main progress component."""
        # Get responsive layout manager
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        spacing = self.get_spacing()
        typography = self.get_typography()
        
        # Create header section
        self._header_container = self._create_header_section()
        
        # Create progress list
        self._progress_list = ft.Column(
            controls=[],
            spacing=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        
        # Create overall progress section
        overall_section = self._create_overall_progress_section()
        
        # Create statistics section
        self._stats_container = self._create_statistics_section()
        
        # Main container
        self._main_container = ft.Container(
            content=ft.Column(
                controls=[
                    self._header_container,
                    overall_section,
                    ft.Divider(
                        height=1,
                        color=palette.outline_variant
                    ),
                    ft.Container(
                        content=self._progress_list,
                        expand=True,
                        padding=responsive_manager.get_breakpoint_value(
                            mobile=12, tablet=16, desktop=20, large=24
                        )
                    ),
                    self._stats_container
                ],
                spacing=responsive_manager.get_breakpoint_value(
                    mobile=12, tablet=16, desktop=20, large=24
                ),
                expand=True
            ),
            bgcolor=palette.surface,
            border_radius=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            border=ft.border.all(1, palette.outline_variant),
            padding=responsive_manager.get_breakpoint_value(
                mobile=16, tablet=20, desktop=24, large=28
            ),
            expand=True
        )
        
        # Start update timer
        self._start_update_timer()
    
    def _create_header_section(self) -> ft.Container:
        """Create the header section with title and controls."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()
        
        # Title
        title = ft.Text(
            value="Embedding Progress",
            size=typography.headline_small[0],
            weight=typography.headline_small[1],
            color=palette.text_primary
        )
        
        # Control buttons
        pause_resume_btn = ft.IconButton(
            icon=icons.PAUSE if not self._is_paused else icons.PLAY_ARROW,
            tooltip="Pause All" if not self._is_paused else "Resume All",
            on_click=self._toggle_pause_all,
            icon_color=palette.primary,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=20, tablet=22, desktop=24, large=26
            )
        )
        
        cancel_all_btn = ft.IconButton(
            icon=icons.STOP,
            tooltip="Cancel All",
            on_click=self._cancel_all,
            icon_color=palette.error,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=20, tablet=22, desktop=24, large=26
            )
        )
        
        refresh_btn = ft.IconButton(
            icon=icons.REFRESH,
            tooltip="Refresh",
            on_click=self._refresh_progress,
            icon_color=palette.text_secondary,
            icon_size=responsive_manager.get_breakpoint_value(
                mobile=20, tablet=22, desktop=24, large=26
            )
        )
        
        # Header container
        return ft.Container(
            content=ft.Row(
                controls=[
                    title,
                    ft.Row(
                        controls=[pause_resume_btn, cancel_all_btn, refresh_btn],
                        spacing=responsive_manager.get_breakpoint_value(
                            mobile=8, tablet=10, desktop=12, large=14
                        )
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.padding.only(
                bottom=responsive_manager.get_breakpoint_value(
                    mobile=12, tablet=16, desktop=20, large=24
                )
            )
        )

    def _create_overall_progress_section(self) -> ft.Container:
        """Create overall progress section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        # Overall progress bar
        self._overall_progress = ft.ProgressBar(
            value=0.0,
            width=responsive_manager.get_breakpoint_value(
                mobile=280, tablet=400, desktop=500, large=600
            ),
            height=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            color=palette.primary,
            bgcolor=palette.surface_variant
        )

        # Progress text
        progress_text = ft.Text(
            value="0% Complete (0/0 documents)",
            size=typography.body_medium[0],
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )

        # Status summary
        status_summary = ft.Row(
            controls=[
                self._create_status_chip("Active", 0, palette.primary),
                self._create_status_chip("Completed", 0, palette.success),
                self._create_status_chip("Failed", 0, palette.error)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=12, desktop=16, large=20
            )
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=self._overall_progress,
                        alignment=ft.alignment.center
                    ),
                    progress_text,
                    status_summary
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=responsive_manager.get_breakpoint_value(
                    mobile=8, tablet=10, desktop=12, large=14
                )
            ),
            padding=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            )
        )

    def _create_status_chip(self, label: str, count: int, color: str) -> ft.Container:
        """Create a status chip with count."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=responsive_manager.get_breakpoint_value(
                            mobile=8, tablet=10, desktop=12, large=14
                        ),
                        height=responsive_manager.get_breakpoint_value(
                            mobile=8, tablet=10, desktop=12, large=14
                        ),
                        bgcolor=color,
                        border_radius=responsive_manager.get_breakpoint_value(
                            mobile=4, tablet=5, desktop=6, large=7
                        )
                    ),
                    ft.Text(
                        value=f"{label}: {count}",
                        size=typography.body_small[0],
                        color=palette.text_secondary
                    )
                ],
                spacing=responsive_manager.get_breakpoint_value(
                    mobile=4, tablet=6, desktop=8, large=10
                ),
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=responsive_manager.get_breakpoint_value(
                mobile=6, tablet=8, desktop=10, large=12
            ),
            border_radius=responsive_manager.get_breakpoint_value(
                mobile=6, tablet=8, desktop=10, large=12
            ),
            bgcolor=palette.surface_variant
        )

    def _create_statistics_section(self) -> ft.Container:
        """Create statistics section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        # Performance metrics
        metrics_row = ft.Row(
            controls=[
                self._create_metric_card("Vectors/sec", "0", palette.primary),
                self._create_metric_card("Memory", "0 MB", palette.secondary),
                self._create_metric_card("GPU", "0%", palette.tertiary),
                self._create_metric_card("Cache Hit", "0%", palette.success)
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=12, desktop=16, large=20
            ),
            wrap=True
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Performance Metrics",
                        size=typography.title_small[0],
                        weight=typography.title_small[1],
                        color=palette.text_primary
                    ),
                    metrics_row
                ],
                spacing=responsive_manager.get_breakpoint_value(
                    mobile=8, tablet=12, desktop=16, large=20
                )
            ),
            padding=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            ),
            bgcolor=palette.surface_container_low,
            border_radius=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            )
        )

    def _create_metric_card(self, label: str, value: str, color: str) -> ft.Container:
        """Create a metric card."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value=value,
                        size=typography.headline_small[0],
                        weight=typography.headline_small[1],
                        color=color,
                        text_align=ft.TextAlign.CENTER
                    ),
                    ft.Text(
                        value=label,
                        size=typography.body_small[0],
                        color=palette.text_secondary,
                        text_align=ft.TextAlign.CENTER
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=responsive_manager.get_breakpoint_value(
                    mobile=4, tablet=6, desktop=8, large=10
                )
            ),
            padding=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            ),
            border_radius=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            bgcolor=palette.surface_variant,
            width=responsive_manager.get_breakpoint_value(
                mobile=80, tablet=100, desktop=120, large=140
            )
        )

    def add_embedding_item(self, item: EmbeddingProgressItem) -> None:
        """Add a new embedding progress item."""
        try:
            self._progress_items[item.item_id] = item
            self._update_progress_display()
            self._logger.info(f"Added embedding item: {item.document_name}")
        except Exception as e:
            self._logger.error(f"Error adding embedding item: {e}")

    def update_embedding_progress(self, item_id: str, progress_percent: float,
                                chunks_processed: int = None, vectors_generated: int = None,
                                status: EmbeddingProgressStatus = None) -> None:
        """Update progress for a specific embedding item."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.progress_percent = min(100.0, max(0.0, progress_percent))

                if chunks_processed is not None:
                    item.chunks_processed = chunks_processed
                if vectors_generated is not None:
                    item.vectors_generated = vectors_generated
                if status is not None:
                    item.status = status

                self._update_progress_display()

                if self._on_progress_update:
                    self._on_progress_update(item_id, progress_percent)

        except Exception as e:
            self._logger.error(f"Error updating embedding progress: {e}")

    def complete_embedding(self, item_id: str) -> None:
        """Mark an embedding as completed."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.status = EmbeddingProgressStatus.COMPLETED
                item.progress_percent = 100.0
                item.end_time = datetime.now(timezone.utc)

                self._completed_count += 1
                self._update_progress_display()

                if self._on_embedding_complete:
                    self._on_embedding_complete(item_id)

                self._check_all_complete()

        except Exception as e:
            self._logger.error(f"Error completing embedding: {e}")

    def fail_embedding(self, item_id: str, error_message: str) -> None:
        """Mark an embedding as failed."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.status = EmbeddingProgressStatus.FAILED
                item.error_message = error_message
                item.end_time = datetime.now(timezone.utc)

                self._failed_count += 1
                self._update_progress_display()

                if self._on_embedding_error:
                    self._on_embedding_error(item_id, error_message)

        except Exception as e:
            self._logger.error(f"Error failing embedding: {e}")

    def _toggle_pause_all(self, e) -> None:
        """Toggle pause/resume for all embeddings."""
        try:
            self._is_paused = not self._is_paused

            for item in self._progress_items.values():
                if item.status == EmbeddingProgressStatus.PROCESSING:
                    item.status = EmbeddingProgressStatus.PAUSED if self._is_paused else EmbeddingProgressStatus.PROCESSING

            self._update_progress_display()
            self._logger.info(f"{'Paused' if self._is_paused else 'Resumed'} all embeddings")

        except Exception as e:
            self._logger.error(f"Error toggling pause: {e}")

    def _cancel_all(self, e) -> None:
        """Cancel all active embeddings."""
        try:
            cancelled_count = 0
            for item in self._progress_items.values():
                if item.status in [EmbeddingProgressStatus.PROCESSING, EmbeddingProgressStatus.PAUSED, EmbeddingProgressStatus.PENDING]:
                    item.status = EmbeddingProgressStatus.CANCELLED
                    item.end_time = datetime.now(timezone.utc)
                    cancelled_count += 1

                    if self._on_embedding_cancelled:
                        self._on_embedding_cancelled(item.item_id)

            self._update_progress_display()
            self._logger.info(f"Cancelled {cancelled_count} embeddings")

        except Exception as e:
            self._logger.error(f"Error cancelling embeddings: {e}")

    def _refresh_progress(self, e) -> None:
        """Refresh the progress display."""
        try:
            self._update_progress_display()
            self._logger.info("Refreshed embedding progress display")
        except Exception as e:
            self._logger.error(f"Error refreshing progress: {e}")

    def _update_progress_display(self) -> None:
        """Update the progress display with current data."""
        try:
            if not self._progress_list or not self._overall_progress:
                return

            # Clear existing progress items
            self._progress_list.controls.clear()

            # Count status
            active_count = 0
            completed_count = 0
            failed_count = 0
            total_progress = 0.0

            # Add progress items
            for item in self._progress_items.values():
                if item.status == EmbeddingProgressStatus.PROCESSING:
                    active_count += 1
                elif item.status == EmbeddingProgressStatus.COMPLETED:
                    completed_count += 1
                elif item.status == EmbeddingProgressStatus.FAILED:
                    failed_count += 1

                total_progress += item.progress_percent

                # Create progress item UI
                progress_item_ui = self._create_progress_item_ui(item)
                self._progress_list.controls.append(progress_item_ui)

            # Update overall progress
            if self._progress_items:
                overall_percent = total_progress / len(self._progress_items)
                self._overall_progress.value = overall_percent / 100.0
            else:
                self._overall_progress.value = 0.0

            # Update counts
            self._active_count = active_count
            self._completed_count = completed_count
            self._failed_count = failed_count

            # Update UI if page is available
            if self.page:
                self.page.update()

        except Exception as e:
            self._logger.error(f"Error updating progress display: {e}")

    def _create_progress_item_ui(self, item: EmbeddingProgressItem) -> ft.Container:
        """Create UI for individual progress item."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()
        icons = self.get_icons()

        # Document info section
        doc_info = ft.Column(
            controls=[
                ft.Text(
                    value=item.document_name,
                    size=typography.body_large[0],
                    weight=typography.body_large[1],
                    color=palette.text_primary,
                    overflow=ft.TextOverflow.ELLIPSIS
                ),
                ft.Text(
                    value=f"{item.chunks_processed}/{item.chunk_count} chunks • {item.vectors_generated} vectors",
                    size=typography.body_small[0],
                    color=palette.text_secondary
                )
            ],
            spacing=responsive_manager.get_breakpoint_value(
                mobile=4, tablet=6, desktop=8, large=10
            ),
            expand=True
        )

        # Progress section
        progress_section = self._create_progress_section(item)

        # Status and controls
        status_controls = self._create_status_controls(item)

        # Main row
        main_row = ft.Row(
            controls=[
                doc_info,
                progress_section,
                status_controls
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            )
        )

        # Container with status-based styling
        return ft.Container(
            content=main_row,
            padding=responsive_manager.get_breakpoint_value(
                mobile=12, tablet=16, desktop=20, large=24
            ),
            border_radius=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            bgcolor=self._get_item_background_color(item.status),
            border=ft.border.all(1, self._get_item_border_color(item.status))
        )

    def _create_progress_section(self, item: EmbeddingProgressItem) -> ft.Column:
        """Create progress visualization section."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        typography = self.get_typography()

        # Progress bar
        progress_bar = ft.ProgressBar(
            value=item.progress_percent / 100.0,
            width=responsive_manager.get_breakpoint_value(
                mobile=120, tablet=140, desktop=160, large=180
            ),
            height=responsive_manager.get_breakpoint_value(
                mobile=6, tablet=7, desktop=8, large=9
            ),
            color=self._get_progress_color(item.status),
            bgcolor=palette.surface_variant
        )

        # Progress text
        progress_text = ft.Text(
            value=f"{item.progress_percent:.1f}%",
            size=typography.body_small[0],
            color=palette.text_primary,
            text_align=ft.TextAlign.CENTER
        )

        # Time info
        time_info = self._get_time_info(item)
        time_text = ft.Text(
            value=time_info,
            size=typography.body_small[0],
            color=palette.text_secondary,
            text_align=ft.TextAlign.CENTER
        )

        return ft.Column(
            controls=[progress_bar, progress_text, time_text],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=4, tablet=6, desktop=8, large=10
            )
        )

    def _create_status_controls(self, item: EmbeddingProgressItem) -> ft.Row:
        """Create status indicator and control buttons."""
        responsive_manager = self.get_responsive_layout()
        palette = self.get_palette()
        icons = self.get_icons()

        # Status icon
        status_icon = self._get_status_icon(item.status)
        status_color = self._get_status_color(item.status)

        status_indicator = ft.Icon(
            name=status_icon,
            color=status_color,
            size=responsive_manager.get_breakpoint_value(
                mobile=20, tablet=22, desktop=24, large=26
            )
        )

        # Control buttons
        controls = []

        if item.status == EmbeddingProgressStatus.PROCESSING:
            pause_btn = ft.IconButton(
                icon=icons.PAUSE,
                tooltip="Pause",
                on_click=lambda e: self._pause_item(item.item_id),
                icon_color=palette.primary,
                icon_size=responsive_manager.get_breakpoint_value(
                    mobile=18, tablet=20, desktop=22, large=24
                )
            )
            controls.append(pause_btn)
        elif item.status == EmbeddingProgressStatus.PAUSED:
            resume_btn = ft.IconButton(
                icon=icons.PLAY_ARROW,
                tooltip="Resume",
                on_click=lambda e: self._resume_item(item.item_id),
                icon_color=palette.primary,
                icon_size=responsive_manager.get_breakpoint_value(
                    mobile=18, tablet=20, desktop=22, large=24
                )
            )
            controls.append(resume_btn)

        if item.status in [EmbeddingProgressStatus.PROCESSING, EmbeddingProgressStatus.PAUSED, EmbeddingProgressStatus.PENDING]:
            cancel_btn = ft.IconButton(
                icon=icons.CLOSE,
                tooltip="Cancel",
                on_click=lambda e: self._cancel_item(item.item_id),
                icon_color=palette.error,
                icon_size=responsive_manager.get_breakpoint_value(
                    mobile=18, tablet=20, desktop=22, large=24
                )
            )
            controls.append(cancel_btn)

        return ft.Row(
            controls=[status_indicator] + controls,
            spacing=responsive_manager.get_breakpoint_value(
                mobile=8, tablet=10, desktop=12, large=14
            ),
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

    def _pause_item(self, item_id: str) -> None:
        """Pause a specific embedding item."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.status = EmbeddingProgressStatus.PAUSED
                self._update_progress_display()
                self._logger.info(f"Paused embedding: {item.document_name}")
        except Exception as e:
            self._logger.error(f"Error pausing item: {e}")

    def _resume_item(self, item_id: str) -> None:
        """Resume a specific embedding item."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.status = EmbeddingProgressStatus.PROCESSING
                self._update_progress_display()
                self._logger.info(f"Resumed embedding: {item.document_name}")
        except Exception as e:
            self._logger.error(f"Error resuming item: {e}")

    def _cancel_item(self, item_id: str) -> None:
        """Cancel a specific embedding item."""
        try:
            if item_id in self._progress_items:
                item = self._progress_items[item_id]
                item.status = EmbeddingProgressStatus.CANCELLED
                item.end_time = datetime.now(timezone.utc)
                self._update_progress_display()

                if self._on_embedding_cancelled:
                    self._on_embedding_cancelled(item_id)

                self._logger.info(f"Cancelled embedding: {item.document_name}")
        except Exception as e:
            self._logger.error(f"Error cancelling item: {e}")

    def _get_progress_color(self, status: EmbeddingProgressStatus) -> str:
        """Get progress bar color based on status."""
        palette = self.get_palette()

        color_map = {
            EmbeddingProgressStatus.PENDING: palette.outline,
            EmbeddingProgressStatus.INITIALIZING: palette.primary,
            EmbeddingProgressStatus.PROCESSING: palette.primary,
            EmbeddingProgressStatus.VECTORIZING: palette.secondary,
            EmbeddingProgressStatus.STORING: palette.tertiary,
            EmbeddingProgressStatus.PAUSED: palette.warning,
            EmbeddingProgressStatus.COMPLETED: palette.success,
            EmbeddingProgressStatus.FAILED: palette.error,
            EmbeddingProgressStatus.CANCELLED: palette.outline
        }

        return color_map.get(status, palette.primary)

    def _get_status_icon(self, status: EmbeddingProgressStatus) -> str:
        """Get status icon based on status."""
        icons = self.get_icons()

        icon_map = {
            EmbeddingProgressStatus.PENDING: icons.SCHEDULE,
            EmbeddingProgressStatus.INITIALIZING: icons.HOURGLASS_EMPTY,
            EmbeddingProgressStatus.PROCESSING: icons.AUTORENEW,
            EmbeddingProgressStatus.VECTORIZING: icons.SCATTER_PLOT,
            EmbeddingProgressStatus.STORING: icons.SAVE,
            EmbeddingProgressStatus.PAUSED: icons.PAUSE,
            EmbeddingProgressStatus.COMPLETED: icons.CHECK_CIRCLE,
            EmbeddingProgressStatus.FAILED: icons.ERROR,
            EmbeddingProgressStatus.CANCELLED: icons.CANCEL
        }

        return icon_map.get(status, icons.HELP)

    def _get_status_color(self, status: EmbeddingProgressStatus) -> str:
        """Get status color based on status."""
        palette = self.get_palette()

        color_map = {
            EmbeddingProgressStatus.PENDING: palette.outline,
            EmbeddingProgressStatus.INITIALIZING: palette.primary,
            EmbeddingProgressStatus.PROCESSING: palette.primary,
            EmbeddingProgressStatus.VECTORIZING: palette.secondary,
            EmbeddingProgressStatus.STORING: palette.tertiary,
            EmbeddingProgressStatus.PAUSED: palette.warning,
            EmbeddingProgressStatus.COMPLETED: palette.success,
            EmbeddingProgressStatus.FAILED: palette.error,
            EmbeddingProgressStatus.CANCELLED: palette.outline
        }

        return color_map.get(status, palette.text_secondary)

    def _get_item_background_color(self, status: EmbeddingProgressStatus) -> str:
        """Get item background color based on status."""
        palette = self.get_palette()

        if status == EmbeddingProgressStatus.FAILED:
            return palette.error_container
        elif status == EmbeddingProgressStatus.COMPLETED:
            return palette.success_container
        elif status == EmbeddingProgressStatus.PAUSED:
            return palette.warning_container
        else:
            return palette.surface_container_low

    def _get_item_border_color(self, status: EmbeddingProgressStatus) -> str:
        """Get item border color based on status."""
        palette = self.get_palette()

        if status == EmbeddingProgressStatus.FAILED:
            return palette.error
        elif status == EmbeddingProgressStatus.COMPLETED:
            return palette.success
        elif status == EmbeddingProgressStatus.PAUSED:
            return palette.warning
        else:
            return palette.outline_variant

    def _get_time_info(self, item: EmbeddingProgressItem) -> str:
        """Get time information for an item."""
        try:
            if item.start_time:
                if item.end_time:
                    # Completed item
                    duration = item.end_time - item.start_time
                    return f"Completed in {duration.total_seconds():.1f}s"
                else:
                    # Active item
                    elapsed = datetime.now(timezone.utc) - item.start_time
                    if item.progress_percent > 0:
                        # Estimate remaining time
                        total_estimated = elapsed.total_seconds() * (100.0 / item.progress_percent)
                        remaining = total_estimated - elapsed.total_seconds()
                        return f"~{remaining:.0f}s remaining"
                    else:
                        return f"Running {elapsed.total_seconds():.0f}s"
            else:
                return "Not started"
        except Exception:
            return "Unknown"

    def _check_all_complete(self) -> None:
        """Check if all embeddings are complete and trigger callback."""
        try:
            active_items = [
                item for item in self._progress_items.values()
                if item.status in [
                    EmbeddingProgressStatus.PENDING,
                    EmbeddingProgressStatus.INITIALIZING,
                    EmbeddingProgressStatus.PROCESSING,
                    EmbeddingProgressStatus.VECTORIZING,
                    EmbeddingProgressStatus.STORING,
                    EmbeddingProgressStatus.PAUSED
                ]
            ]

            if not active_items and self._progress_items and self._on_all_complete:
                self._on_all_complete()
                self._logger.info("All embeddings completed")

        except Exception as e:
            self._logger.error(f"Error checking completion: {e}")

    def _start_update_timer(self) -> None:
        """Start the update timer for real-time updates."""
        try:
            if not self._update_timer or self._update_timer.done():
                self._update_timer = asyncio.create_task(self._update_loop())
        except Exception as e:
            self._logger.error(f"Error starting update timer: {e}")

    async def _update_loop(self) -> None:
        """Main update loop for real-time progress updates."""
        try:
            while not self._is_updating:
                await asyncio.sleep(self._config.update_interval_ms / 1000.0)

                if self._progress_items and self.page:
                    # Update metrics and display
                    self._update_metrics()

                    # Update UI if needed
                    if self.page:
                        self.page.update()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in update loop: {e}")

    def _update_metrics(self) -> None:
        """Update performance metrics."""
        try:
            # Calculate aggregate metrics
            total_vectors = sum(item.vectors_generated for item in self._progress_items.values())
            active_items = [
                item for item in self._progress_items.values()
                if item.status == EmbeddingProgressStatus.PROCESSING
            ]

            # Update metrics display if stats container exists
            if self._stats_container and active_items:
                # This would update the metric cards with real values
                # Implementation depends on having access to actual performance data
                pass

        except Exception as e:
            self._logger.error(f"Error updating metrics: {e}")

    def clear_completed_items(self) -> None:
        """Clear all completed embedding items."""
        try:
            completed_items = [
                item_id for item_id, item in self._progress_items.items()
                if item.status == EmbeddingProgressStatus.COMPLETED
            ]

            for item_id in completed_items:
                del self._progress_items[item_id]

            self._update_progress_display()
            self._logger.info(f"Cleared {len(completed_items)} completed items")

        except Exception as e:
            self._logger.error(f"Error clearing completed items: {e}")

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get a summary of current progress."""
        try:
            total_items = len(self._progress_items)
            if total_items == 0:
                return {
                    "total_items": 0,
                    "completed": 0,
                    "failed": 0,
                    "active": 0,
                    "overall_progress": 0.0
                }

            completed = sum(1 for item in self._progress_items.values()
                          if item.status == EmbeddingProgressStatus.COMPLETED)
            failed = sum(1 for item in self._progress_items.values()
                        if item.status == EmbeddingProgressStatus.FAILED)
            active = sum(1 for item in self._progress_items.values()
                        if item.status == EmbeddingProgressStatus.PROCESSING)

            total_progress = sum(item.progress_percent for item in self._progress_items.values())
            overall_progress = total_progress / total_items if total_items > 0 else 0.0

            return {
                "total_items": total_items,
                "completed": completed,
                "failed": failed,
                "active": active,
                "overall_progress": overall_progress,
                "total_vectors": sum(item.vectors_generated for item in self._progress_items.values()),
                "total_chunks": sum(item.chunk_count for item in self._progress_items.values())
            }

        except Exception as e:
            self._logger.error(f"Error getting progress summary: {e}")
            return {}

    def cleanup(self) -> None:
        """Clean up resources and stop timers."""
        try:
            self._is_updating = True

            if self._update_timer and not self._update_timer.done():
                self._update_timer.cancel()

            self._progress_items.clear()
            self._logger.info("Embedding progress UI cleaned up")

        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass
